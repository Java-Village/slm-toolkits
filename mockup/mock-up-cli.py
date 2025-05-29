import requests
import json
from datetime import datetime

def print_response(response):
    """格式化並打印響應"""
    print("\n=== 響應 ===")
    print(f"狀態: {response['status']}")
    print(f"時間戳: {response['timestamp']}")
    print(f"訊息: {response['message']}")
    print("\n=== 數據 ===")
    print(json.dumps(response['data'], indent=2, ensure_ascii=False))
    print("===========\n")

def main():
    print("歡迎使用模擬協調伺服器 CLI")
    print("輸入 'quit' 或 'exit' 退出")
    
    while True:
        command = input("\n請輸入命令: ").strip()
        
        if command.lower() in ['quit', 'exit']:
            break
            
        if not command:
            continue
            
        try:
            response = requests.post(
                "http://localhost:5000/api/command",
                json={"command": command}
            )
            print_response(response.json())
        except Exception as e:
            print(f"錯誤: {str(e)}")

if __name__ == "__main__":
    main() 