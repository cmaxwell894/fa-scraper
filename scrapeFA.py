from playwright.async_api import async_playwright
from typing import Literal
import asyncio
import time
import os

__all__ = ["scrapeFA"]

class scrapeFA:
    @staticmethod
    async def _main_getTeamsByLeagueNames(
        league_data,
        show_browser: bool = False,
        skip_if_multiple: bool = False,
        log_if_state: Literal["error", "skipped", "all"] = "error",
        report_file: str = "output/scrapeFA_report.txt",
        output_file: str = "output/scrapeFA_output.txt",
        return_report: bool = False  # new flag
    ) -> list[str]:

        os.makedirs("output", exist_ok=True)

        # ================= Helper functions =================
        class fm:
            @staticmethod
            def writeData(teams: list[str], report: dict, deltaTime: float = 0):
                if output_file:
                    with open(output_file, "a") as file:
                        file.writelines(f"{x}\n" for x in teams)
                if report_file:
                    with open(report_file, "a") as file:
                        minutes, seconds = divmod(deltaTime, 60)
                        file.write(f"Time taken: {int(minutes)} minutes, {round(seconds)} seconds\n")
                        file.writelines(generateReport(report))

            @staticmethod
            def clearData():
                if output_file:
                    open(output_file, "w").close()
                if report_file:
                    open(report_file, "w").close()

        def generateReport(report: dict) -> str:
            output = f"Total entries: {report['total_teams_found']}\n\n\n"
            for entry in report["log"]:
                output += f"> League Name: {entry['name']}\n"
                output += f"  Leagues Found: {entry['leagues_found']}\n"
                output += f"  Divisions Scanned: {entry['divisions_found']}\n"
                output += f"  Skipped: {'Yes' if entry['skipped'] else 'No'}\n\n"
            if len(report["log"]) == 0:
                output += "All quiet here... for now\n"
            return output        

        # ================= Main scraping logic =================
        async def worker(pw, show_browser: bool=False):
            browser  = await pw.chromium.launch(headless = not show_browser)
            page     = await browser.new_page()
            all_teams, final_report = await startWorkingWithLeagueNames(page, league_data)
            await browser.close()
            return all_teams, final_report

        async def startWorkingWithLeagueNames(page, league_names) -> list[str]:
            searchResultsYes    = page.locator("div.search-results").locator("*").first
            rejectAll           = page.get_by_role("button", name="Reject All")
            divisionPicker      = page.locator("#form1_selectedDivision")
            teamsButton         = page.locator("div", has_text="Latest").get_by_role("link", name="Teams", exact=True)
            teamsNamesElements  = page.locator('[class="team-and-form grid-2"]').get_by_role("link").locator("h4")

            output: list[str] = []
            report: dict = {"total_teams_found": 0, "log": []}

            for iName in league_names:
                await page.goto("https://fulltime.thefa.com/home/search.html")
                if await rejectAll.count() > 0: 
                    await rejectAll.click()

                await page.get_by_placeholder("ABC").fill(iName)
                await page.keyboard.press("Enter")
                await searchResultsYes.wait_for(state="visible")

                leaguesFoundCount = await page.get_by_role("link", name=iName).count()

                if leaguesFoundCount < 1:
                    report["log"].append({"name": iName, "leagues_found": 0, "skipped": True, "divisions_found": 0})
                    continue
                if leaguesFoundCount > 1 and skip_if_multiple:
                    report["log"].append({"name": iName, "leagues_found": leaguesFoundCount, "skipped": True, "divisions_found": 0})
                    continue

                await page.get_by_role("link", name=iName).first.click()
                await divisionPicker.wait_for(state="visible")

                div_number = await divisionPicker.locator("option").count()
                if ((log_if_state == "error" and leaguesFoundCount>1) or (log_if_state == "all")):
                    report["log"].append({"name": iName, "leagues_found": leaguesFoundCount, "skipped": False, "divisions_found": div_number})

                for i in range(div_number):
                    await divisionPicker.select_option(index=i)
                    await teamsButton.wait_for(state="visible")
                    await teamsButton.click()
                    teamsNames = await teamsNamesElements.all_text_contents()
                    output.extend(teamsNames)
                    report["total_teams_found"] += len(teamsNames)

            return sorted(output), report

        # ================= Run =================
        print(">>> Running the scraper...")
        if not isinstance(league_data, list) or len(league_data) < 1:
            print("(!) League data must be a non-empty list")
            return

        fm.clearData()
        start_time = time.time()

        async with async_playwright() as pw:
            teams, report = await worker(pw, show_browser)

        deltaTime = time.time() - start_time
        fm.writeData(teams, report, deltaTime)
        print(">>> Done!")

        if return_report:
            return teams, report
        return teams

    @staticmethod
    def getTeamsByLeagueNames(
        league_data,
        show_browser: bool = False,
        skip_if_multiple: bool = True,
        log_if_state: Literal["error", "skipped", "all"] = "error",
        report_file: str = "output/scrapeFA_report.txt",
        output_file: str = "output/scrapeFA_output.txt",
        return_report: bool = False,  # new flag
    ):
        return asyncio.run(scrapeFA._main_getTeamsByLeagueNames(
            league_data,
            show_browser,
            skip_if_multiple,
            log_if_state,
            report_file,
            output_file,
            return_report
        ))
