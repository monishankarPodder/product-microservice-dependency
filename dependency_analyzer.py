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
    <title>Dependency Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #2a5699; }}
        code {{ background-color: #eee; padding: 3px 6px; border-radius: 4px; }}
        ul {{ padding-left: 20px; }}
        table {{ border-collapse: collapse; background: white; width: 100%; }}
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

def find_method_end_line(code, start_line):
    """
    Approximate method end by counting braces from start line.
    """
    lines = code.split("\n")[start_line - 1 :]
    start = 0
    brace_count = 0
    for idx, line in enumerate(lines):
        start += 1
        for c in line:
            if c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
        if brace_count <= 0 and idx > 0:
            break
    return start_line + start - 1

def find_changed_methods_from_git():
    result = subprocess.run(
        ["git", "diff", "-U0", "HEAD~1", "HEAD", "--", "*.java"],
        stdout=subprocess.PIPE,
        text=True
    )
    diff = result.stdout

    file_changes = {}  # file -> set of changed line numbers
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
                    file_changes[current_file].add(i)

    changed_methods = set()

    for file, lines in file_changes.items():
        path = os.path.join(".", file)
        if not os.path.exists(path):
            continue  # skip deleted files
        with open(path, "r") as f:
            code = f.read()

        try:
            tree = javalang.parse.parse(code)
        except:
            continue

        for _, node in tree.filter(javalang.tree.MethodDeclaration):
            if hasattr(node, "position") and node.position:
                start_line = node.position.line
                end_line = find_method_end_line(code, start_line)
                for l in lines:
                    if start_line <= l <= end_line:
                        changed_methods.add(node.name)
                        break

    return list(changed_methods)

def find_dependents(methods, inv_graph):
    visited = set()
    stack = list(methods)

    while stack:
        method = stack.pop()
        for dep in inv_graph.get(method, []):
            if dep not in visited:
                visited.add(dep)
                stack.append(dep)
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

def render_testcases(tcs):
    return "\n".join(f"<tr><td>{tc['id']}</td><td>{tc['name']}</td><td>{tc['folder']}</td></tr>" for tc in tcs)

if __name__ == "__main__":
    SRC_DIR = "./src/main/java/com/example/product"
    TESTCASE_FILE = "./testcases.json"

    print("🔍 Parsing Java files and tracking method usage...")
    dependency_graph = build_dependency_graph(SRC_DIR)
    inverse = inverse_graph(dependency_graph)

    print("🔍 Detecting changed methods...")
    changed_methods = find_changed_methods_from_git()
    dependent_methods = list(find_dependents(changed_methods, inverse))
    all_methods = sorted(set(changed_methods + dependent_methods))

    print("🔍 Matching test cases from testcases.json...")
    with open(TESTCASE_FILE) as f:
        testcases = json.load(f)

    matched_testcases = find_testcases(all_methods, testcases)

    # HTML output
    html = HTML_TEMPLATE.format(
        changed=render_list(changed_methods),
        dependents=render_list(dependent_methods),
        testcases=render_testcases(matched_testcases)
    )

    with open("dependency_report.html", "w") as out:
        out.write(html)

    print("✅ Dependency report generated: dependency_report.html")
