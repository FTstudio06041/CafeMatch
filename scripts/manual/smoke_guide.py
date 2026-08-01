import sys; sys.path.append('services'); from conversation_guide import analyze_and_guide; print(analyze_and_guide([{'role': 'user', 'content': '推薦咖啡廳'}], {'preferences':{}}))
