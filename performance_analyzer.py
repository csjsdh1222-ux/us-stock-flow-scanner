import pandas as pd
import yfinance as yf
from datetime import timedelta

LOG_FILE = "logs/daily_candidates.csv"


def get_return_after_days(ticker, signal_date, days=1):
    try:
        start_date = pd.to_datetime(signal_date)
        end_date = start_date + timedelta(days=days + 7)

        data = yf.Ticker(ticker).history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d")
        )

        if data.empty or len(data) < 2:
            return None

        entry_price = data["Close"].iloc[0]
        exit_price = data["Close"].iloc[min(days, len(data) - 1)]

        return round((exit_price - entry_price) / entry_price * 100, 2)

    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None


def analyze_performance():
    df = pd.read_csv(LOG_FILE)

    if df.empty:
        print("분석할 데이터가 없습니다.")
        return

    results = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        signal_date = row["date"]

        return_1d = get_return_after_days(ticker, signal_date, days=1)
        return_3d = get_return_after_days(ticker, signal_date, days=3)
        return_5d = get_return_after_days(ticker, signal_date, days=5)

        results.append({
            "date": signal_date,
            "ticker": ticker,
            "sector": row["sector"],
            "score": row["score"],
            "label": row["label"],
            "return_1d": return_1d,
            "return_3d": return_3d,
            "return_5d": return_5d,
        })

    result_df = pd.DataFrame(results)

    result_df.to_csv("logs/performance_report.csv", index=False, encoding="utf-8-sig")

    print("\n[PERFORMANCE REPORT]")
    print(result_df)

    valid = result_df.dropna(subset=["return_1d"])

    if not valid.empty:
        winrate_1d = (valid["return_1d"] > 0).mean() * 100
        avg_return_1d = valid["return_1d"].mean()

        print("\n[SUMMARY]")
        print(f"1D 승률: {winrate_1d:.2f}%")
        print(f"1D 평균 수익률: {avg_return_1d:.2f}%")

    print("\n성과 분석 저장 완료 → logs/performance_report.csv")


if __name__ == "__main__":
    analyze_performance()