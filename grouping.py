# grouping.py
import pandas as pd
import re
import json

# =========================
# Load keywords for grouping
# =========================
with open("keywords.json", "r") as f:
    keywords_data = json.load(f)

youth_keywords = keywords_data["youth_keywords"]
mens_keywords = keywords_data["mens_keywords"]
ladies_keywords = keywords_data["ladies_keywords"]
color_keywords = keywords_data["color_keywords"]
disability_keywords = keywords_data["disability_keywords"]
abbreviation_map = keywords_data["abbreviation_map"]
club_suffixes = keywords_data["club_suffixes"]

all_keywords = set(youth_keywords + mens_keywords + ladies_keywords + color_keywords + disability_keywords)

# =========================
# Clean club names
# =========================
def clean_club_name(name, abbreviation_map):
    for abbr, full in abbreviation_map.items():
        name = re.sub(r'\b' + re.escape(abbr) + r'\b', full, name, flags=re.IGNORECASE)
    name_norm = re.sub(r'\bF\.?C\.?\b', '', name, flags=re.IGNORECASE)
    name_norm = re.sub(r'\bAFC\b', '', name_norm, flags=re.IGNORECASE)
    name_norm = re.sub(r'[.,]$', '', name_norm)
    name_norm = re.sub(r'\s+', ' ', name_norm).strip()
    return name_norm

# =========================
# Base club name extraction
# =========================
def get_base_club_name(team_name, age_pattern, youth_keywords, all_keywords, club_suffixes):
    dash_parts = [p.strip() for p in team_name.split('-')]
    base_part = dash_parts[0]
    words = base_part.split()
    base_name_parts = []

    for word in words:
        if age_pattern.search(word) or word in youth_keywords or word in all_keywords:
            break
        base_name_parts.append(word)

    if words and words[-1] in club_suffixes and words[-1] not in base_name_parts:
        base_name_parts.append(words[-1])

    if not base_name_parts:
        base_name_parts = words[:1]

    return " ".join(base_name_parts).strip()

# =========================
# Normalize club names
# =========================
def normalize_club_name_for_merge(club_name):
    club_name = club_name.upper().replace('.', '')
    club_name = re.sub(r'\s+', ' ', club_name).strip()
    club_name = re.sub(r'\b(JF?C?|F C|F C)\b', 'FC', club_name)
    return club_name

def safe_normalize_club_name(club_name):
    match = re.match(
        r'^(?P<main>.+?)(?:\s+(?P<suffix>(Junior|Youth|U\d+|1st|2nd|Reserves|Colts|Development|Rangers).*)?)?$',
        club_name,
        re.IGNORECASE
    )
    if match:
        main_club = match.group('main').strip()
        suffix = match.group('suffix') or ''
        main_club_norm = normalize_club_name_for_merge(main_club)
        return f"{main_club_norm} {suffix}".strip()
    else:
        return normalize_club_name_for_merge(club_name)

# =========================
# Merge teams
# =========================
def merge_teams(grouped_teams):
    merged_grouped = {}
    for key, teams in grouped_teams.items():
        if '(' in key:
            club, category = key.rsplit('(', 1)
            category = category.rstrip(')').strip()
            club = club.strip()
        else:
            club = key
            category = ""
        base_match = re.match(
            r'^(.+?)(\s+(Junior|Youth|U\d+|1st|2nd|Rangers|Reserves|Development|Colts).*)?$',
            club,
            re.IGNORECASE
        )
        if base_match:
            merged_name = safe_normalize_club_name(base_match.group(1) + (base_match.group(2) or ""))
        else:
            merged_name = safe_normalize_club_name(club)
        merged_key = f"{merged_name} ({category})" if category else merged_name
        merged_grouped.setdefault(merged_key, []).extend(teams)
    return {k: sorted(v) for k, v in merged_grouped.items()}

# =========================
# Main function for grouping
# =========================
def process_teams_list(teams_list):
    grouped_teams = {}
    age_pattern = re.compile(r'\bU\d+', re.IGNORECASE)

    # Detect exact duplicates first
    team_series = pd.Series(teams_list)
    duplicates = team_series[team_series.duplicated(keep=False)].reset_index(drop=True)
    unique_teams = team_series.drop_duplicates().tolist()

    for team in unique_teams:
        if not team.strip():
            continue
        original_team = team
        team_cleaned = clean_club_name(team, abbreviation_map)

        # Determine category
        if age_pattern.search(team_cleaned) or re.search(r'\b(?:' + '|'.join(youth_keywords) + r')\b', team_cleaned):
            category = "Youth"
            club_name = get_base_club_name(team_cleaned, age_pattern, youth_keywords, all_keywords, club_suffixes)
        else:
            if re.search(r'\b(?:' + '|'.join(ladies_keywords) + r')\b', team_cleaned, flags=re.IGNORECASE):
                category = "Ladies"
            elif re.search(r'\b(?:' + '|'.join(mens_keywords) + r')\b', team_cleaned, flags=re.IGNORECASE):
                category = "Mens"
            elif re.search(r'\b(?:' + '|'.join(disability_keywords) + r')\b', team_cleaned, flags=re.IGNORECASE):
                category = "Disability"
            else:
                category = "Mens"
            club_name = get_base_club_name(team_cleaned, age_pattern, all_keywords, all_keywords, club_suffixes)

        fc_prefix = ''
        fc_match = re.match(r'^(F\.?C\.?)\s+', original_team)
        if fc_match:
            fc_prefix = fc_match.group(1) + ' '

        display_club_name = f"{fc_prefix}{club_name}"
        key = f"{safe_normalize_club_name(display_club_name)} ({category})"
        grouped_teams.setdefault(key, []).append(original_team)

    # Merge similar teams
    grouped_teams = merge_teams(grouped_teams)

    # Build main grouped DataFrame
    grouped_list = [[k, len(v), ", ".join(v)] for k, v in sorted(grouped_teams.items())]
    grouped_df = pd.DataFrame(grouped_list, columns=["Club (Category)", "Team Count", "Teams"])

    # Build duplicates DataFrame
    if not duplicates.empty:
        dup_counts = duplicates.value_counts().reset_index()
        dup_counts.columns = ["Team Name", "Occurrences"]
        dup_counts = dup_counts[dup_counts["Occurrences"] > 1]
    else:
        dup_counts = pd.DataFrame(columns=["Team Name", "Occurrences"])

    return grouped_df, dup_counts

