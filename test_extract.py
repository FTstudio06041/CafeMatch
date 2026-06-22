import json
with open(r'C:\Users\user\.gemini\antigravity\brain\c6697aaf-c01f-48e4-b7dd-f607e9aa2929\.system_generated\tasks\task-299.log', 'r', encoding='utf-8') as f:
    text = f.read()
    import re
    chunks = re.findall(r''(\{.*?\})'', text)
    for c in chunks:
        try:
            j = json.loads(c)
            if 'response' in j:
                print(j['response'], end='')
        except:
            pass
print()
