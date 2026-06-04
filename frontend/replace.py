import os
import re

base = r'c:\Users\user\Desktop\CafeMatch_local\frontend\src'

for root, dirs, files in os.walk(base):
    for f in files:
        if f.endswith('.jsx') or f.endswith('.js'):
            path = os.path.join(root, f)
            if 'logger.js' in f or 'toast.js' in f or 'apiClient.js' in f: continue
            
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            orig_content = content
            
            # replace alert
            content = re.sub(r'\bwindow\.alert\(', 'toast.info(', content)
            content = re.sub(r'\balert\(', 'toast.info(', content)
            
            # replace console.log / error
            content = re.sub(r'\bconsole\.log\(', 'logger.info(', content)
            content = re.sub(r'\bconsole\.error\(', 'logger.error(', content)
            
            if content != orig_content:
                # determine relative path
                rel = os.path.relpath(base, root).replace('\\', '/')
                prefix = './utils/' if rel == '.' else rel + '/utils/'
                
                imports_to_add = []
                if 'toast.' in content and 'import { toast }' not in content:
                    imports_to_add.append(f"import {{ toast }} from '{prefix}toast';")
                if 'logger.' in content and 'import { logger }' not in content:
                    imports_to_add.append(f"import {{ logger }} from '{prefix}logger';")
                
                if imports_to_add:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if not line.startswith('import ') and line.strip() != '':
                            lines.insert(i, '\n'.join(imports_to_add))
                            break
                    content = '\n'.join(lines)
                
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(content)
