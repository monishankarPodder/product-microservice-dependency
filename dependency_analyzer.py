import os
import json
import re
import javalang
import subprocess

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dependency Report</title>
<style>
    body {{ font-family: sans-serif; padding: 20px; background: #f5f5f5; }}
    h1 {{ color: #2a5699; }}
    code {{ background-color: #e3e3e3; padding: 3px 6px; border-radius: 4px; }}
    ul {{ padding-left: 20px; }}
    table {{ border-collapse: collapse; background: white; width: 100%; max-width: 800px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
    th {{ background-color: #2a5699; color: white; }}
</style>
</head>
<body>
<h1>Dependency Analysis Report</h1>

<h2>Changed Methods</h2>
<ul>{changed}</ul>

<h2>Dependent Methods</h2>
<ul>{dependents}</ul>

<h2>Associated Test Cases</h2>
<table>
    <tr><th>ID</th><th>Name</th><th>Folder</th></tr>
    {testcases}
</table>

</body>
</html>
"""

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
    method_defs = {}

    for file in find_java_files(src_dir):
        for method_name, node, _ in parse_methods(file):
            method_defs[method_name] = node

    for file in find_java_files(src_dir):
        for caller, caller_node, _ in parse_methods(file):
            callees = set()
            for path, node in caller_node:
                if isinstance(node, javalang.tree.MethodInvocation):
                    callees.add(node.member)
            graph[caller] = list(callees)
    return graph

def inverse_graph(graph):
    inv = {}
    for caller, callees in graph.items():
        for callee in callees:
            inv.setdefault(callee, []).append(caller)
    return inv

def find_changed_methods_from_git():
    result = subprocess.run(
        ["git", "diff", "-U0", "HEAD~1", "HEAD"],
        stdout=subprocess.PIPE,
        text=True
    )
    diff = result.stdout
    method_pattern = re.compile(r"\b(public|private|protected)?\s*(static\s*)?[\w<>]+\s+(\w+)\s*\(.*?\)\s*[{;]?")
    changed = set()
    for line in diff.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            line = line[1:].strip()
            match = method_pattern.search(line)
            if match:
                method_name = match.group(3)
                changed.add(method_name)
    return list(changed)

def find_dependents(methods, inv_graph):
    visited = set()
    stack = list(methods)

    while stack:
        method = stack.pop()
        for dependent in inv_graph.get(method, []):
            if dependent not in visited:
                visited.add(dependent)
                stack.append(dependent)
    return visited

def find_testcases(methods, testcases):
    matched = []
    norm_methods = [m.lower() for m in methods]
    for tc in testcases:
        name = tc['name'].lower()
        if any(m in name for m in norm_methods):
            matched.append(tc)
    return matched

def render_list(items):
    return "\n".join(f"<li><code>{item}</code></li>" for item in items)

def render_testcase_rows(tcs):
    return "\n".join(
        f"<tr><td>{tc['id']}</td><td>{tc['name']}</td><td>{tc['folder']}</td></tr>"
        for tc in tcs
    )

if __name__ == "__main__":
    SRC = "./src/main/java/com/example/product"
    TESTCASE_FILE = "./testcases.json"

    print("🔍 Scanning Java methods and computing dependencies...")
    dep_graph = build_dependency_graph(SRC)
    inv_graph = inverse_graph(dep_graph)

    print("⏳ Detecting changed methods using Git diff...")
    changed_methods = find_changed_methods_from_git()
    dependents = list(find_dependents(changed_methods, inv_graph))
    all_methods = set(changed_methods + dependents)

    with open(TESTCASE_FILE) as f:
        testcases = json.load(f)

    matched_testcases = find_testcases(all_methods, testcases)

    # Output HTML report
    html = HTML_TEMPLATE.format(
        changed=render_list(changed_methods),
        dependents=render_list(dependents),
        testcases=render_testcase_rows(matched_testcases)
    )

    with open("dependency_report.html", "w") as f:
        f.write(html)

    print("✅ Analysis complete. Report generated at: dependency_report.html")
