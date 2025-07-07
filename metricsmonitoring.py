import subprocess
import pandas as pd
import re
from datetime import datetime
import requests
import yaml
import io
import logging
import os
import shutil
from dotenv import load_dotenv
import traceback
import matplotlib.pyplot as plt
from PIL import Image
import base64
import json

# Load environment variables from .env file
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_CHANNEL = "#pantheonmetricsalerts"
ENV = "live"
YAML_FILE = "sites.yaml"
LOG_FILE = "metricsmonitoring.log"
ALERT_LOG_FILE = "alert_log.json"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def resolve_terminus_command():
    terminus_cmd = shutil.which("terminus") or os.getenv("TERMINUS_COMMAND")
    if not terminus_cmd:
        raise FileNotFoundError("Could not find 'terminus' command and 'TERMINUS_COMMAND' is not set.")
    return terminus_cmd

def load_config(yaml_file):
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    return config.get("sites_to_monitor", []), config.get("threshold_percent", 25)

def send_slack_notification(message, blocks=None):
    if not SLACK_WEBHOOK_URL or "hooks.slack.com/services/" not in SLACK_WEBHOOK_URL:
        print("Slack webhook URL is not set or invalid. Please update SLACK_WEBHOOK_URL in your .env file.")
        return False
    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logging.info("Slack notification sent successfully.")
            print("Slack notification sent successfully.")
            return True
        else:
            logging.error(f"Slack notification failed with status code {response.status_code}.")
            print(f"Slack notification failed with status code {response.status_code}.")
            return False
    except Exception as e:
        logging.error(f"Error sending Slack notification: {e}")
        print(f"Error sending Slack notification: {e}")
        return False

def get_sites(sites_to_monitor):
    try:
        terminus_cmd = resolve_terminus_command()
        result = subprocess.run(
            [terminus_cmd, "site:list", "--format=csv"],
            capture_output=True, text=True, check=True
        )
        df = pd.read_csv(io.StringIO(result.stdout))
        return df[df["Name"].isin(sites_to_monitor)]
    except Exception as e:
        logging.error(f"Error getting sites: {e}")
        print(f"Error getting sites: {e}")
        return pd.DataFrame()

def get_metrics(site_name, env, period):
    try:
        terminus_cmd = resolve_terminus_command()
        command = [
            terminus_cmd, "env:metrics",
            "--period", period,
            "--datapoints", "auto",
            "--format", "table",
            "--fields", "Period,Visits,Pages Served,Cache Hits,Cache Misses,Cache Hit Ratio,HTTP 4xx,HTTP 5xx",
            "--",
            f"{site_name}.{env}"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        logging.error(f"Error getting metrics for {site_name}: {e}")
        print(f"Error getting metrics for {site_name}: {e}")
        return ""

def parse_table_to_df(output):
    try:
        lines = output.splitlines()
        header_idx = next((i for i, line in enumerate(lines) if "Period" in line and "Cache Hit Ratio" in line), None)
        if header_idx is None:
            return None
        header = re.split(r'\s{2,}', lines[header_idx].strip())
        data = []
        for line in lines[header_idx+2:]:
            if not line.strip() or line.strip().startswith("-"):
                continue
            row = re.split(r'\s{2,}', line.strip())
            if len(row) == len(header):
                data.append(row)
        if not data:
            return None
        df = pd.DataFrame(data, columns=header)
        for col in ["Visits", "Pages Served", "Cache Hits", "Cache Misses", "HTTP 4xx", "HTTP 5xx"]:
            if col in df.columns:
                df[col] = df[col].str.replace(",", "").astype(int)
        df["Cache Hit Ratio"] = df["Cache Hit Ratio"].str.replace("%", "").astype(float)
        try:
            df["Period"] = pd.to_datetime(df["Period"], format="%Y-%m-%d")
        except Exception:
            pass
        return df
    except Exception as e:
        logging.error(f"Error parsing metrics table: {e}")
        print(f"Error parsing metrics table: {e}")
        return None

def load_alert_log():
    if os.path.exists(ALERT_LOG_FILE):
        with open(ALERT_LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_alert_log(log):
    with open(ALERT_LOG_FILE, "w") as f:
        json.dump(log, f)

def already_alerted(site_name, alert_type, date_str):
    log = load_alert_log()
    key = f"{site_name}:{alert_type}:{date_str}"
    return log.get(key, False)

def mark_alerted(site_name, alert_type, date_str):
    log = load_alert_log()
    key = f"{site_name}:{alert_type}:{date_str}"
    log[key] = True
    save_alert_log(log)

def send_trend_chart_to_slack(site_name, df, dashboard_url):
    # Only plot last 14 days for clarity
    trend_df = df.tail(14)
    plt.figure(figsize=(8, 3))
    plt.plot(trend_df["Period"], trend_df["Visits"], marker='o', color='blue')
    plt.title(f"Visits Trend: {site_name}")
    plt.xlabel("Date")
    plt.ylabel("Visits")
    plt.grid(True)
    plt.tight_layout()
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    # Save locally
    filename = f"{site_name}_trend.png"
    with open(filename, "wb") as f:
        f.write(buf.read())
    print(f"Saved trend chart for {site_name} as {filename}")
    # Notify in Slack (image upload via webhook is not supported)
    send_slack_notification(
        f"Traffic trend for {site_name} (see attached chart or local file `{filename}`)\n<{dashboard_url}|View in Pantheon Dashboard>"
    )

def monitor_sites():
    try:
        print(f"Starting metrics monitoring script (period: day)...")
        logging.info(f"Script started (period: day).")
        sites_to_monitor, threshold_percent = load_config(YAML_FILE)
        sites_df = get_sites(sites_to_monitor)
        if sites_df.empty:
            logging.warning("No sites found to monitor after filtering.")
            print("No sites found to monitor after filtering.")
        for _, row in sites_df.iterrows():
            site_name = row["Name"]
            site_id = row["ID"]
            print(f"Checking site: {site_name} ...")
            logging.info(f"Checking site: {site_name}")
            metrics_output = get_metrics(site_name, ENV, "day")
            df = parse_table_to_df(metrics_output)
            if df is not None and "Visits" in df.columns and len(df) > 4:
                recent = df.iloc[-1]
                recent_visits = recent["Visits"]
                recent_date = recent["Period"].strftime('%Y-%m-%d')
                recent_day_name = recent["Period"].strftime('%A')
                dashboard_url = f"https://dashboard.pantheon.io/sites/{site_id}#{ENV}/code"

                # --- Trend Visualization ---
                send_trend_chart_to_slack(site_name, df, dashboard_url)

                # --- Traffic Spike Alert with Fatigue Prevention ---
                previous_days = df.iloc[-6:-1]  # last 5 days before today
                if len(previous_days) >= 3:
                    avg_visits = previous_days["Visits"].mean()
                    prev_periods = previous_days["Period"].dt.strftime('%Y-%m-%d').tolist()
                    prev_visits = previous_days["Visits"].tolist()
                else:
                    avg_visits = df["Visits"].iloc[:-1].mean()
                    prev_periods = df["Period"].iloc[:-1].dt.strftime('%Y-%m-%d').tolist()
                    prev_visits = df["Visits"].iloc[:-1].tolist()

                percent_increase = ((recent_visits - avg_visits) / avg_visits) * 100 if avg_visits > 0 else 0

                prev_days = [pd.to_datetime(d).strftime('%A') for d in prev_periods]
                blocks = [
                    {"type": "header", "text": {"type": "plain_text", "text": "🚨 Anomalous Traffic Detected!"}},
                    {"type": "section", "fields": [
                        {"type": "mrkdwn", "text": f"*Site:*\n{site_name} ({ENV})"},
                        {"type": "mrkdwn", "text": f"*Date:*\n{recent_date} ({recent_day_name})"},
                        {"type": "mrkdwn", "text": f"*Recent Visits:*\n{recent_visits:,}"},
                        {"type": "mrkdwn", "text": f"*Average (last 5 days):*\n{avg_visits:,.2f}"},
                        {"type": "mrkdwn", "text": f"*Increase:*\n{percent_increase:.1f}%"},
                        {"type": "mrkdwn", "text": f"*Threshold:*\n{threshold_percent}%"},
                    ]},
                    {"type": "section", "text": {"type": "mrkdwn", "text": "*Previous days:*"}},
                    {"type": "context", "elements": [
                        {"type": "mrkdwn", "text": "\n".join([f"{d} ({day}): {v:,} visits" for d, day, v in zip(prev_periods, prev_days, prev_visits)])}
                    ]},
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"<{dashboard_url}|View in Pantheon Dashboard>"}}
                ]
                alert_date = recent_date
                if not already_alerted(site_name, "traffic_spike", alert_date):
                    if avg_visits > 0 and recent_visits > avg_visits * (1 + threshold_percent / 100):
                        print(f"Anomaly detected for {site_name}! Sending Slack alert...")
                        logging.info(f"Anomaly detected for {site_name}: {percent_increase:.1f}% increase. Sending alert.")
                        send_slack_notification("Anomalous Traffic Detected!", blocks=blocks)
                        mark_alerted(site_name, "traffic_spike", alert_date)
                    else:
                        print(f"No anomaly detected for {site_name}.")
                        logging.info(f"No anomaly detected for {site_name}.")
                else:
                    print(f"Already alerted for traffic spike on {site_name} for {alert_date}.")

                # --- Error/Status Monitoring with Fatigue Prevention ---
                if "HTTP 4xx" in df.columns and "HTTP 5xx" in df.columns:
                    recent_4xx = df.iloc[-1]["HTTP 4xx"]
                    recent_5xx = df.iloc[-1]["HTTP 5xx"]
                    error_alert_type = "error_rate"
                    error_threshold_4xx = 100  # Adjust as needed
                    error_threshold_5xx = 10   # Adjust as needed
                    if not already_alerted(site_name, error_alert_type, alert_date):
                        if recent_4xx > error_threshold_4xx or recent_5xx > error_threshold_5xx:
                            error_blocks = [
                                {"type": "header", "text": {"type": "plain_text", "text": "🚨 High Error Rate Detected!"}},
                                {"type": "section", "fields": [
                                    {"type": "mrkdwn", "text": f"*Site:*\n{site_name} ({ENV})"},
                                    {"type": "mrkdwn", "text": f"*Date:*\n{recent_date} ({recent_day_name})"},
                                    {"type": "mrkdwn", "text": f"*HTTP 4xx:*\n{recent_4xx:,}"},
                                    {"type": "mrkdwn", "text": f"*HTTP 5xx:*\n{recent_5xx:,}"},
                                ]},
                                {"type": "section", "text": {"type": "mrkdwn", "text": f"<{dashboard_url}|View in Pantheon Dashboard>"}}
                            ]
                            send_slack_notification("High Error Rate Detected!", blocks=error_blocks)
                            mark_alerted(site_name, error_alert_type, alert_date)
                        else:
                            print(f"No high error rate detected for {site_name}.")
                    else:
                        print(f"Already alerted for error rate on {site_name} for {alert_date}.")

                # --- Cache hit ratio alert (unchanged) ---
                avg_ratio = df["Cache Hit Ratio"].mean() if not df.empty else 0
                if avg_ratio < 50:
                    if avg_ratio >= 80:
                        indicator = "🟢"
                    elif avg_ratio >= 50:
                        indicator = "🟡"
                    else:
                        indicator = "🔴"
                    trend_df = df.tail(5)
                    trend_text = "\n".join([
                        f"{row['Period'].strftime('%Y-%m-%d')}: {row['Cache Hit Ratio']:.0f}%"
                        for _, row in trend_df.iterrows()
                    ])
                    worst_row = trend_df.loc[trend_df['Cache Hit Ratio'].idxmin()]
                    worst_text = f"{worst_row['Cache Hit Ratio']:.0f}% ({worst_row['Period'].strftime('%Y-%m-%d')})"
                    recent_misses = df.iloc[-1]["Cache Misses"]
                    impact_text = f"{recent_misses:,} extra origin requests (last period)"
                    cache_blocks = [
                        {"type": "header", "text": {"type": "plain_text", "text": f"{indicator} Low Cache Efficiency Detected!"}},
                        {"type": "section", "fields": [
                            {"type": "mrkdwn", "text": f"*Site:*\n{site_name} ({ENV})"},
                            {"type": "mrkdwn", "text": f"*Average Cache Hit Ratio:*\n{avg_ratio:.2f}%"},
                            {"type": "mrkdwn", "text": "*Threshold:*\n50%"},
                            {"type": "mrkdwn", "text": f"*Origin Requests:*\n{impact_text}"},
                        ]},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Recent Cache Hit Ratios:*\n{trend_text}"}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Lowest Ratio in Last 5 Periods:* {worst_text}"}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": (
                            "*How to improve caching efficiency:*\n"
                            "• Ensure static assets (images, CSS, JS) are cacheable and have long cache lifetimes.\n"
                            "• Review HTTP headers (`Cache-Control`, `Expires`).\n"
                            "• Avoid unnecessary cache bypass for dynamic pages.\n"
                            "• Use Pantheon’s [Advanced Page Cache](https://pantheon.io/docs/advanced-page-cache).\n"
                            "• Avoid uncacheable cookies or query parameters.\n"
                            "• Audit for personalized content and use `Vary` headers if needed."
                        )}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"<{dashboard_url}|View in Pantheon Dashboard>"}}
                    ]
                    print(f"Low cache efficiency detected for {site_name}! Sending Slack alert...")
                    logging.info(f"Low cache efficiency detected for {site_name}: {avg_ratio:.2f}%. Sending alert.")
                    send_slack_notification("Low Cache Efficiency Detected!", blocks=cache_blocks)

            else:
                print(f"Could not parse metrics for {site_name}.")
                logging.warning(f"Could not parse metrics for {site_name}.")
        print("Metrics monitoring script finished.")
        logging.info("Script finished.")
    except Exception as e:
        error_message = f":x: *Metrics Monitoring Script Error!*\n```\n{traceback.format_exc()}\n```"
        print("An error occurred! Sending Slack alert.")
        logging.error(f"Unhandled exception: {traceback.format_exc()}")
        send_slack_notification(error_message)

if __name__ == "__main__":
    monitor_sites()
