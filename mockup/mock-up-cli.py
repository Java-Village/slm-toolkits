import requests
import json
from datetime import datetime
import sys
import time
import threading
import random

def loading_animation(stop_event):
    """顯示載入動畫"""
    animation = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write("\r" + "Waiting for the LLM response... " + animation[idx % len(animation)])
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 20 + "\r")  # 清除動畫

def stream_response(content):
    """模擬串流效果，逐字顯示內容"""
    words = content.split()
    for word in words:
        print(word, end=' ', flush=True)
        # 隨機延遲 0.05 到 0.15 秒，模擬真實打字效果
        time.sleep(random.uniform(0.05, 0.15))
    print()  # 最後換行

def print_response(response):
    print("\n=== Response ===")
    content = response['data']['llm_response']['choices'][0]['message']['content']
    stream_response(content)
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