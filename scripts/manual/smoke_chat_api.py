import requests, json; r = requests.post("http://127.0.0.1:5000/api/chat", json={"message":"哈囉","history":[]}, stream=True); print([line.decode() for line in r.iter_lines() if line])
