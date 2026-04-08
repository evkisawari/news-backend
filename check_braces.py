def check_braces(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    stack = []
    for i, line in enumerate(lines, 1):
        for char in line:
            if char == '{':
                stack.append(i)
            elif char == '}':
                if not stack:
                    print(f"Extra closing brace at line {i}")
                else:
                    stack.pop()
    
    if stack:
        print(f"Unclosed braces opened at lines: {stack}")
    else:
        print("Braces are balanced")

if __name__ == "__main__":
    check_braces(r'c:\Users\dparw\Desktop\news app\lib\providers\app_provider.dart')
