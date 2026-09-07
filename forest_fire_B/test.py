# test_api.py
import requests
import time
import json

BASE_URL = "http://localhost:8100"

def test_simulate():
    print("🚀 开始测试火灾模拟接口...")
    
    # 1. 触发模拟
    payload = {
        "fire_point": [114.3, 30.5],
        "wind_speed": 15,
        "wind_dir": 90,
        "terrain": "mountain"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/simulate/", json=payload)
        if resp.status_code != 200:
            print(f"❌ 触发失败: {resp.text}")
            return
        
        data = resp.json()
        task_id = data['task_id']
        print(f"✅ 任务已启动, ID: {task_id}")
        
        # 2. 轮询查询结果
        print("⏳ 等待模拟计算中 (预计3-5秒)...")
        for i in range(10):
            time.sleep(1)
            res_resp = requests.get(f"{BASE_URL}/simulate/result/{task_id}")
            if res_resp.status_code == 200:
                result_data = res_resp.json()
                if result_data['status'] == 'completed':
                    print("🎉 模拟完成！结果如下:")
                    print(json.dumps(result_data, indent=2, ensure_ascii=False))
                    return
                elif result_data['status'] == 'failed':
                    print(f"❌ 模拟失败: {result_data.get('error')}")
                    return
            print(f"   ... 正在查询第 {i+1} 次")
            
        print("⚠️ 超时：模拟未在预期时间内完成")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    test_simulate()
