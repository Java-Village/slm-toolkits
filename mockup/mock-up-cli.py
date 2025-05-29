import requests
import json
from datetime import datetime
import sys
import time
import threading

def loading_animation(stop_event):
    """顯示載入動畫"""
    animation = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write("\r" + "等待回應中 " + animation[idx % len(animation)])
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 20 + "\r")  # 清除動畫

def print_response(response):
    print("\n=== Response ===")
    print(f"Message: {response['data']['llm_response']['choices'][0]['message']['content']}")
    print("===========\n")

def main():
    print("Welcome to Mock Coordination Server CLI")
    print("Type 'quit' or 'exit' to exit")
    
    while True:
        command = input("\nEnter command: ").strip()
        
        if command.lower() in ['quit', 'exit']:
            break
            
        if not command:
            continue
            
        try:
            # 創建停止事件
            stop_event = threading.Event()
            # 啟動載入動畫
            loading_thread = threading.Thread(target=loading_animation, args=(stop_event,))
            loading_thread.start()
            
            # 發送請求
            response = requests.post(
                "http://localhost:5000/api/command",
                json={"command": command}
            )
            
            # 停止動畫
            stop_event.set()
            loading_thread.join()
            
            print_response(response.json())
        except Exception as e:
            # 確保在發生錯誤時也停止動畫
            if 'stop_event' in locals():
                stop_event.set()
                loading_thread.join()
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 