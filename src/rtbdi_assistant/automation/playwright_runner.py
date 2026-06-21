from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from rtbdi_assistant.config import AssistantConfig
from rtbdi_assistant.models import DateRange, Report


@dataclass(frozen=True)
class BrowserConfig:
    base_url: str = "https://www.myrtpos.com/newbdi/"
    login_path: str = "index.fwx"
    headless: bool = True
    username: str | None = None
    password: str | None = None
    storage_state: Path | None = None
    downloads_dir: Path = Path("downloads")

    @classmethod
    def from_env(cls, *, headless: bool = True, downloads_dir: Path | None = None) -> "BrowserConfig":
        config = AssistantConfig.from_env()
        return cls(
            base_url=config.rtbdi_base_url,
            headless=headless,
            username=config.rtbdi_username,
            password=config.rtbdi_password,
            storage_state=config.rtbdi_storage_state,
            downloads_dir=downloads_dir or cls.downloads_dir,
        )


class PlaywrightReportRunner:
    """Executes mapped reports against the live RT BDI site.

    The class is intentionally selector-light until live credentials/session testing
    is available. Public methods encode the required behavior: always set dates,
    apply report-specific filters, generate, and read grid or export according to
    the knowledge map.
    """

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "PlaywrightReportRunner":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        kwargs: dict[str, Any] = {"accept_downloads": True}
        if self.config.storage_state:
            kwargs["storage_state"] = str(self.config.storage_state)
        self._context = await self._browser.new_context(**kwargs)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Runner has not been started")
        return await self._context.new_page()

    def _base_directory(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.casefold().endswith(".fwx"):
            return base_url.rsplit("/", 1)[0]
        return base_url

    def _login_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.casefold().endswith(".fwx"):
            return base_url
        return f"{base_url}/{self.config.login_path.lstrip('/')}"

    async def login(self, page: Page) -> None:
        if not self.config.username or not self.config.password:
            raise RuntimeError("RTBDI_USERNAME and RTBDI_PASSWORD must be set for login")

        await page.goto(self._login_url(), wait_until="domcontentloaded")
        if await page.get_by_text("LOGOUT", exact=False).count():
            return

        await self._fill_first(
            page,
            (
                "input[name*='user' i]",
                "input[id*='user' i]",
                "input[name*='login' i]",
                "input[type='text']",
            ),
            self.config.username,
        )
        await self._fill_first(page, ("input[type='password']", "input[name*='pass' i]", "input[id*='pass' i]"), self.config.password)

        login_button = page.locator("button, input[type='submit'], input[type='button']").filter(has_text="Login").first
        if await login_button.count():
            await login_button.click()
        else:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")

        if await page.locator("input[type='password']").count() and not await page.get_by_text("LOGOUT", exact=False).count():
            raise RuntimeError("RT BDI login did not reach an authenticated page")

    async def save_storage_state(self, path: Path) -> None:
        if not self._context:
            raise RuntimeError("Runner has not been started")
        path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(path))

    async def _fill_first(self, page: Page, selectors: tuple[str, ...], value: str) -> None:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count():
                await locator.fill(value)
                return
        raise RuntimeError(f"Could not find input for selectors: {', '.join(selectors)}")

    async def open_report(self, page: Page, report: Report) -> None:
        if report.url_path:
            await page.goto(self._base_directory() + "/" + report.url_path.lstrip("/"), wait_until="domcontentloaded")
            return

        await page.goto(self._login_url(), wait_until="domcontentloaded")
        href = await page.locator("a").filter(has_text=report.name).first.get_attribute("href")
        if href:
            await page.goto(urljoin(page.url, href), wait_until="domcontentloaded")
            return
        await page.get_by_text(report.tab, exact=True).hover()
        await page.locator("a").filter(has_text=report.name).first.click()
        await page.wait_for_load_state("domcontentloaded")

    async def set_date_range(self, page: Page, report_range: DateRange) -> None:
        # The site uses a date picker; direct input is more stable than clicking calendar cells.
        rendered = f"{report_range.start:%B %-d, %Y} - {report_range.end:%B %-d, %Y}"
        hidden_start = page.locator("#frmStart, input[name='frmStart']").first
        hidden_end = page.locator("#frmEnd, input[name='frmEnd']").first
        if await hidden_start.count() and await hidden_end.count():
            await page.evaluate(
                """({start, end, rendered}) => {
                    const assign = (selector, value) => {
                        const input = document.querySelector(selector);
                        if (!input) return;
                        input.value = value;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    };
                    assign("#frmStart, input[name='frmStart']", start);
                    assign("#frmEnd, input[name='frmEnd']", end);
                    const range = document.querySelector("#reportrange span") || document.querySelector("#reportrange");
                    if (range) range.textContent = rendered;
                }""",
                {
                    "start": f"{report_range.start:%m/%d/%Y}",
                    "end": f"{report_range.end:%m/%d/%Y}",
                    "rendered": rendered,
                },
            )
            return

        candidates = [
            "input[name*='ReportRange']",
            "input[name*='daterange']",
            "input[id*='ReportRange']",
            "input[id*='date']",
        ]
        for selector in candidates:
            locator = page.locator(selector).first
            if await locator.count():
                await locator.fill(rendered)
                return
        raise RuntimeError("Could not find a date range input on the report page")

    async def select_filter(self, page: Page, label_or_name: str, value: str) -> None:
        # RT BDI screenshots show Select2-style dropdowns. This method first tries
        # accessible labels, then falls back to Select2's search box pattern.
        try:
            await page.get_by_label(label_or_name).select_option(label=value)
            return
        except Exception:
            pass
        await page.locator(".select2-selection").filter(has_text=label_or_name).click()
        search = page.locator("input.select2-search__field").last
        await search.fill(value)
        await page.keyboard.press("Enter")

    async def generate(self, page: Page) -> None:
        button = page.locator(".refresh-button").filter(has_text="Generate").first
        if not await button.count():
            button = page.get_by_text("Generate", exact=True).last
        await button.click()
        await page.wait_for_load_state("networkidle")

    async def download_export(self, page: Page) -> Path:
        self.config.downloads_dir.mkdir(parents=True, exist_ok=True)
        async with page.expect_download() as download_info:
            export_button = page.locator(".export-xlsx-button").first
            if not await export_button.count():
                export_button = page.locator("button, input[type='button'], a, div").filter(has_text="Excel").first
            if not await export_button.count():
                export_button = page.locator("button, input[type='button'], a, div").filter(has_text="Export").first
            await export_button.click()
        download = await download_info.value
        target = self.config.downloads_dir / download.suggested_filename
        await download.save_as(target)
        return target
