import os
import json
import re
import javalang
import subprocess

# HTML TEMPLATE FOR REPORT
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dependency Analysis Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f4f4f4; }}
    h1 {{ color: #2a5699; }}
    h2 {{ margin-top: 30px; }}
    code {{ background: #eee; padding: 3px 5px; border-radius: 3px; }}
    ul {{ padding-left: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background: #2a5699; color: white; }}
  </style>
</head>
<body>
  <h1>Dependency Analysis Report</h1>
  <h2>Changed Methods</h2>
  <ul>
    {changed}
  </ul>
  <h2>Dependent Methods</h2>
  <ul>
    {dependents}
  </ul>
  <h2>Associated Test Cases</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>Name</th><th>Folder</th></tr>
    </thead>
    <tbody>
      {testcases}
    </tbody>
  </table>
</body>
</html>
"""

# === UTILITY FUNCTIONS ===

def find_java_files(src_dir):
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".java"):
                yield os.path.join(root, file)

def parse_methods(file_path):
    with open(file_path) as f:
        code = f.read()

    try:
        tree = javalang.parse.parse(code)
    except:
        return []

    methods = []
    for _, node in tree.filter(javalang.tree.MethodDeclaration):
        methods.append((node.name, node, file_path))
    return methods

def build_dependency_graph(src_dir):
    graph = {}
    for file in find_java_files(src_dir):
        for caller, node, _ in parse_methods(file):
            callees = set()
            for path, descendant in node:
                if isinstance(descendant, javalang.tree.MethodInvocation):
                    callees.add(descendant.member.strip())
            graph[caller] = list(callees)
    return graph

def inverse_graph(graph):
    inv = {}
    for caller, callees in graph.items():
        for callee in callees:
            inv.setdefault(callee, []).append(caller)
    return inv

def find_method_end_line(code, start_line):
    lines = code.split("\n")[start_line - 1 :]
    brace_count = 0
    for i, line in enumerate(lines):
        for c in line:
            if c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
        if brace_count <= 0 and i > 0:
            return start_line + i
    return start_line + len(lines)

def find_changed_methods_from_git():
    result = subprocess.run(
        ["git", "diff", "-U0", "HEAD~1", "HEAD", "--", "*.java"],
        stdout=subprocess.PIPE,
        text=True
    )
    diff = result.stdout

    file_changes = {}
    current_file = None

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            file_changes[current_file] = set()
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2) or "1")
                for i in range(start, start + count):
                    file_changes.setdefault(current_file, set()).add(i)

    changed_methods = set()

    for file, changed_lines in file_changes.items():
        path = os.path.join(".", file)
        if not os.path.exists(path): continue
        with open(path) as f:
            code = f.read()
        try:
            tree = javalang.parse.parse(code)
        except:
            continue
        for _, node in tree.filter(javalang.tree.MethodDeclaration):
            if node.position:
                start_line = node.position.line
                end_line = find_method_end_line(code, start_line)
                if any(start_line <= l <= end_line for l in changed_lines):
                    changed_methods.add(node.name)
    return list(changed_methods)

def find_dependents(methods, inv_graph):
    visited = set()
    stack = list(methods)
    while stack:
        current = stack.pop()
        for parent in inv_graph.get(current, []):
            if parent not in visited:
                visited.add(parent)
                stack.append(parent)
    return visited

#  SMART TEST CASE MATCHING: TOKEN BASED
def split_camel_case(name):
    # Split camelCase or PascalCase into individual lowercase words
    return [token.lower() for token in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name)]

def find_testcases(methods, testcases):
    matched = []
    norm_method_tokens = set()

    print("🔍 Matching test cases with method tokens...")

    for m in methods:
        tokens = split_camel_case(m)
        print(f"⚙️ Tokenizing method: {m} ➤ Extracted tokens: {tokens}")
        norm_method_tokens.update(tokens)

    print(f"All method tokens to match: {norm_method_tokens}")

    for tc in testcases:
        name = tc["name"].lower()
        print(f"🔎 Checking test case: {tc['id']} - {tc['name']}")
        for token in norm_method_tokens:
            if token in name:
                print(f" ✅ MATCHED on token: {token}")
                matched.append(tc)
                break
        else:
            print(" ❌ No match.")
    return matched




# HTML RENDER HELPERS
def render_list(items):
    return "\n".join(f"<li><code>{item}</code></li>" for item in items)

def render_testcases(tcs):
    return "\n".join(
        f"<tr><td>{tc['id']}</td><td>{tc['name']}</td><td>{tc['folder']}</td></tr>"
        for tc in tcs
    )

# ==== MAIN ====
if __name__ == "__main__":
    SRC_DIR = "./src/main/java/com/example/product"
    TESTCASE_FILE = "./testcases.json"

    print("🔍 Analyzing dependencies...")
    dep_graph = build_dependency_graph(SRC_DIR)
    inv_graph = inverse_graph(dep_graph)

    print("🔍 Detecting changed methods...")
    changed = find_changed_methods_from_git()
    dependents = list(find_dependents(changed, inv_graph))

    all_methods = set(changed) | set(dependents)

    print("📦 Matching test cases...")
    with open(TESTCASE_FILE) as f:
        testcases = json.load(f)

    matched_tcs = find_testcases(all_methods, testcases)

    html = HTML_TEMPLATE.format(
        changed=render_list(changed),
        dependents=render_list(dependents),
        testcases=render_testcases(matched_tcs)
    )

    with open("dependency_report.html", "w") as f:
        f.write(html)

    print("✅ Analysis complete: dependency_report.html generated!")
