from flask import Flask, request, render_template, send_file, Response, stream_with_context
import pandas as pd
import os
import tempfile
from scrapeFA import scrapeFA
from grouping import process_teams_list

app = Flask(__name__)

TMP_DIR = tempfile.mkdtemp()
last_output_file = None
missing_leagues_file = None
SCRAPED_TEAMS = []   # scraped teams across requests
MISSING_LEAGUES = [] # leagues that failed

# Global queue for live logs
LOG_QUEUE = []

# =========================
# SSE stream for live logs
# =========================
@app.route("/logs")
def stream_logs():
    def event_stream():
        last_index = 0
        while True:
            if last_index < len(LOG_QUEUE):
                for i in range(last_index, len(LOG_QUEUE)):
                    yield f"data: {LOG_QUEUE[i]}\n\n"
                last_index = len(LOG_QUEUE)
            else:
                import time
                time.sleep(0.5)
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# =========================
# Home route
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    global last_output_file, missing_leagues_file, SCRAPED_TEAMS, MISSING_LEAGUES, LOG_QUEUE
    LOG_QUEUE = []

    if request.method == "POST":
        if "file" not in request.files:
            LOG_QUEUE.append("No file uploaded")
            return render_template("index.html")

        file = request.files["file"]
        if file.filename == "":
            LOG_QUEUE.append("No file selected")
            return render_template("index.html")

        input_path = os.path.join(TMP_DIR, file.filename)
        file.save(input_path)
        LOG_QUEUE.append(f"Uploaded file: {file.filename}")

        # Read leagues
        df = pd.read_excel(input_path)
        if "Source_URL" not in df.columns:
            LOG_QUEUE.append("Excel must contain a 'Source_URL' column")
            return render_template("index.html")

        leagues = df["Source_URL"].dropna().tolist()
        LOG_QUEUE.append(f"{len(leagues)} leagues found")

        SCRAPED_TEAMS = []
        MISSING_LEAGUES = []

        # Scrape leagues one by one for live logging
        for idx, league in enumerate(leagues, 1):
            LOG_QUEUE.append(f"[{idx}/{len(leagues)}] Processing league: {league}")
            try:
                teams = scrapeFA.getTeamsByLeagueNames([league], show_browser=False)
                if not teams:
                    MISSING_LEAGUES.append(league)
                    LOG_QUEUE.append(f"  ❌ No teams found for this league")
                else:
                    SCRAPED_TEAMS.extend(teams)
                    LOG_QUEUE.append(f"  ✅ {len(teams)} teams found")
            except Exception as e:
                MISSING_LEAGUES.append(league)
                LOG_QUEUE.append(f"  ⚠ Error scraping league: {e}")

        if not SCRAPED_TEAMS and not MISSING_LEAGUES:
            LOG_QUEUE.append("No teams were collected from any league")
            return render_template("index.html")

        # If some leagues are missing → pause for manual input
        if MISSING_LEAGUES:
            LOG_QUEUE.append("Some leagues had no teams. Please add them manually below.")
            return render_template(
                "index.html",
                last_output_file=None,
                missing_leagues_file=None,
                show_manual_input=True,
                missing_leagues=MISSING_LEAGUES
            )

        # Otherwise, finalize grouping immediately
        return finalize_grouping(SCRAPED_TEAMS)

    return render_template(
        "index.html",
        last_output_file=last_output_file,
        missing_leagues_file=missing_leagues_file,
        show_manual_input=False,
        missing_leagues=[]
    )

# =========================
# Manual input route
# =========================
@app.route("/manual_input", methods=["POST"])
def manual_input():
    global SCRAPED_TEAMS, MISSING_LEAGUES, last_output_file, missing_leagues_file, LOG_QUEUE
    LOG_QUEUE.append("Processing manual input...")

    manual_text = request.form.get("manual_teams", "")
    manual_teams = [t.strip() for t in manual_text.splitlines() if t.strip()]

    all_teams = SCRAPED_TEAMS + manual_teams
    return finalize_grouping(all_teams)

# =========================
# Helper: Finalize grouping
# =========================
def finalize_grouping(teams):
    global last_output_file, missing_leagues_file, MISSING_LEAGUES, LOG_QUEUE

    LOG_QUEUE.append("Grouping teams...")
    grouped_df, duplicates_df = process_teams_list(teams)

    last_output_file = os.path.join(TMP_DIR, "grouped_output.xlsx")
    with pd.ExcelWriter(last_output_file) as writer:
        grouped_df.to_excel(writer, sheet_name="Grouped Teams", index=False)
        if duplicates_df is not None and not duplicates_df.empty:
            duplicates_df.to_excel(writer, sheet_name="Exact Duplicates", index=False)
    LOG_QUEUE.append(f"Grouped Excel saved: {last_output_file}")

    # Save missing leagues Excel if any
    if MISSING_LEAGUES:
        missing_leagues_file = os.path.join(TMP_DIR, "missing_leagues.xlsx")
        pd.DataFrame({"Missing League": MISSING_LEAGUES}).to_excel(missing_leagues_file, index=False)
        LOG_QUEUE.append(f"{len(MISSING_LEAGUES)} leagues had no teams and saved to missing_leagues.xlsx")
    else:
        missing_leagues_file = None

    LOG_QUEUE.append("✅ Processing complete!")

    return render_template(
        "index.html",
        last_output_file=last_output_file,
        missing_leagues_file=missing_leagues_file,
        show_manual_input=False,
        missing_leagues=[]
    )

# =========================
# Download route
# =========================
@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(TMP_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

# =========================
# Run
# =========================
port = int(os.environ.get("PORT", 5000))
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)
