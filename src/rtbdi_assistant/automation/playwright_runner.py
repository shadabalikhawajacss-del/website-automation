from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from rtbdi_assistant.models import DateRange, Report


@dataclass(frozen=True)
class BrowserConfig:
    base_url: str = "https://www.myrtpos.com/newbdi/"
    headless: bool = True
    storage_state: Path | None = None
    downloads_dir: Path = Path("downloads")


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

    async def open_report(self, page: Page, report: Report) -> None:
        if report.url_path:
            await page.goto(self.config.base_url.rstrip("/") + "/" + report.url_path.lstrip("/"), wait_until="domcontentloaded")
            return

        await page.goto(self.config.base_url, wait_until="domcontentloaded")
        await page.get_by_text(report.tab, exact=True).hover()
        await page.get_by_text(report.name, exact=True).click()
        await page.wait_for_load_state("domcontentloaded")

    async def set_date_range(self, page: Page, report_range: DateRange) -> None:
        # The site uses a date picker; direct input is more stable than clicking calendar cells.
        rendered = f"{report_range.start:%B %-d, %Y} - {report_range.end:%B %-d, %Y}"
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
        await page.get_by_role("button", name="Generate").click()
        await page.wait_for_load_state("networkidle")

    async def download_export(self, page: Page) -> Path:
        self.config.downloads_dir.mkdir(parents=True, exist_ok=True)
        async with page.expect_download() as download_info:
            export_button = page.locator("button, input[type='button'], a").filter(has_text="Excel").first
            if not await export_button.count():
                export_button = page.locator("button, input[type='button'], a").filter(has_text="Export").first
            await export_button.click()
        download = await download_info.value
        target = self.config.downloads_dir / download.suggested_filename
        await download.save_as(target)
        return target
