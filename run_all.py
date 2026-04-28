import subprocess
import sys
from datetime import datetime


def run_script(script_name):
    print("\n" + "=" * 60)
    print(f"START: {script_name}")
    print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, script_name],
        text=True
    )

    if result.returncode != 0:
        print(f"\nERROR: {script_name} 실행 실패")
        return False

    print(f"\nDONE: {script_name}")
    return True


def main():
    print("\n[US STOCK FLOW AUTO RUNNER]")
    print("Step 1: main.py 실행 → 후보 생성/CSV 저장/텔레그램 알림")
    print("Step 2: alpaca_auto_trader.py 실행 → Paper 자동매매")
    print("Step 3: performance_optimizer.py 실행 → 성과 분석/전략 최적화")

    if not run_script("main.py"):
        print("main.py 실패 → 자동매매 중단")
        return

    if not run_script("alpaca_auto_trader.py"):
        print("alpaca_auto_trader.py 실패")
        return

    if not run_script("performance_optimizer.py"):
        print("performance_optimizer.py 실패")
        return

    print("\n전체 자동 실행 완료")


if __name__ == "__main__":
    main()