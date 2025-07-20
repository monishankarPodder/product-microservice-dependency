import os
import json
import javalang

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dependency Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f9f9f9; }}
        h1 {{ color: #2a5699; }}
        .section {{ margin-bottom: 32px; }}
        table {{ border-collapse: collapse; min-width: 400px; background: #fff; box-shadow: 0 0 4px #eee; }}
        th, td {{
            border: 1px solid #e3e3e3;
            padding: 0.75em 1.2em;
            text-align: left;
        }}
        th {{
            background: #2a5699;
            color: #fff;
            letter-spacing: 0.5px;
        }}
        td {{
            background: #f5f8ff;
        }}
        ul {{ padding-left: 2em; }}
        .testcase-id {{ font-weight: bold; color: #007298; }}
        .button {{
            background: #2a5699;
            color: #fff;
            border: none;
            padding: 10px 18px;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            margin-bottom: 24px;
        }}
        .button:hover {{
            background: #3767b6;
        }}
    </style>
</head>
<body>
    <h1>Dependency Analysis Report</h1>
    <button class="button" onclick="downloadHTML()">Download this report</button>
    <div class="section">
        <h2>Changed Methods</h2>
        <ul>
            {changed_html}
        </ul>
    </div>
    <div class="section">
        <h2>Dependent Methods</h2>
        <ul>
            {dependents_html}
        </ul>
    </div>
    <div class="section">
        <h2>Associated Test Cases</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Folder</th>
                </tr>
            </thead>
            <tbody>
                {testcases_html}
            </tbody>
        </table>
    </div>
    <script>
        function downloadHTML() {{
            // Download this HTML as a file
            const htmlContent = document.documentElement.outerHTML;
            const blob = new Blob([htmlContent], {{ type: "text/html" }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'dependency_report.html';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
    </script>
</body>
</html>
"""

def find_java_files(src_dir):
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.java'):
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
    file_methods = {}
    for f in find_java_files(src_dir):
        for mname, mnode, fpath in parse_methods(f):
            file_methods[mname] = (fpath, mnode)
    for f in find_java_files(src_dir):
        for caller_name, caller_node, fpath in parse_methods(f):
            callees = set()
            for path, node in caller_node:
                if isinstance(node, javalang.tree.MethodInvocation):
                    if node.member in file_methods:
                        callees.add(node.member)
            graph[caller_name] = list(callees)
    return graph

def inverse_graph(graph):
    inverse = {k: [] for k in graph}
    for caller, callees in graph.items():
        for callee in callees:
            inverse.setdefault(callee, []).append(caller)
    return inverse

def find_changed_methods():
    # For demo: Assume these are changed. In real CI, get this from git diff.
    return ["delete", "remove"]

def find_dependents(methods, inv_graph):
    dependents = set()
    stack = list(methods)
    while stack:
        cur = stack.pop()
        for dep in inv_graph.get(cur, []):
            if dep not in dependents:
                dependents.add(dep)
                stack.append(dep)
    return dependents

def match_testcases(methods, testcases):
    hits = []
    search = [m.lower() for m in methods]
    for tc in testcases:
        name = tc['name'].lower()
        if any(m in name for m in search):
            hits.append(tc)
    return hits

def html_list(items):
    return "\n".join(f"<li><code>{item}</code></li>" for item in items)

def html_table_rows(testcases):
    return "\n".join(
        f"<tr><td class=\"testcase-id\">{tc['id']}</td><td>{tc['name']}</td><td>{tc['folder']}</td></tr>"
        for tc in testcases
    )

if __name__ == '__main__':
    src_dir = './src/main/java/com/example/product'
    testcases_path = './testcases.json'
    dep_graph = build_dependency_graph(src_dir)
    inv_graph = inverse_graph(dep_graph)
    changed_methods = find_changed_methods()
    dependents = find_dependents(changed_methods, inv_graph)
    methods_of_interest = set(changed_methods) | set(dependents)
    with open(testcases_path) as f:
        testcases = json.load(f)
    hits = match_testcases(methods_of_interest, testcases)

    # Generate HTML report
    html = HTML_TEMPLATE.format(
        changed_html=html_list(changed_methods),
        dependents_html=html_list(dependents),
        testcases_html=html_table_rows(hits)
    )
    with open("dependency_report.html", "w") as f:
        f.write(html)
