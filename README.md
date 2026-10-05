<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Houdini OpenGL Flipbook Submitter – README.md</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent: #58a6ff;
    --accent-dim: #1f6feb;
    --green: #3fb950;
    --orange: #d29922;
    --code-bg: #0d1117;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
  }

  .readme {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2.5rem;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }

  h1 {
    font-size: 1.85rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    letter-spacing: -0.02em;
  }

  .subtitle {
    color: var(--text-muted);
    font-size: 1.05rem;
    margin-bottom: 1.75rem;
  }

  h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-top: 2.25rem;
    margin-bottom: 0.85rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
    color: var(--accent);
  }

  h3 {
    font-size: 1.05rem;
    font-weight: 600;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
  }

  p { margin-bottom: 1rem; }

  ul, ol {
    margin: 0.5rem 0 1rem 1.4rem;
  }

  li { margin-bottom: 0.35rem; }

  code {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.88em;
    background: rgba(110, 118, 129, 0.2);
    padding: 0.15em 0.4em;
    border-radius: 4px;
  }

  pre {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    overflow-x: auto;
    margin: 1rem 0;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.82rem;
    line-height: 1.55;
  }

  pre code {
    background: none;
    padding: 0;
  }

  .tree {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.85rem;
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
    white-space: pre;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.92rem;
  }

  th, td {
    border: 1px solid var(--border);
    padding: 0.6rem 0.9rem;
    text-align: left;
  }

  th {
    background: rgba(88, 166, 255, 0.08);
    font-weight: 600;
    color: var(--accent);
  }

  tr:nth-child(even) td {
    background: rgba(255,255,255,0.02);
  }

  .badge {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.2em 0.55em;
    border-radius: 999px;
    background: rgba(63, 185, 80, 0.15);
    color: var(--green);
    margin-right: 0.4rem;
  }

  .note {
    background: rgba(210, 153, 34, 0.1);
    border-left: 3px solid var(--orange);
    padding: 0.75rem 1rem;
    border-radius: 0 6px 6px 0;
    margin: 1rem 0;
    font-size: 0.92rem;
  }

  .footer {
    margin-top: 2.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="readme">

<h1>Houdini OpenGL Flipbook Submitter</h1>
<p class="subtitle">
  A Houdini Digital Asset (HDA) integration and Python toolset designed to streamline 
  OpenGL flipbook rendering and Deadline submission directly within SideFX Houdini.
</p>

<span class="badge">Live Reload</span>
<span class="badge">Deadline</span>
<span class="badge">OpenGL Flipbook</span>

<h2>Overview</h2>
<p>
  This repository contains the external Python scripts that drive the Houdini Digital Asset (HDA).
  The asset acts as a lightweight interface, delegating execution and logic to an external module 
  location (<code>$HDA_SCRIPTS</code>) to enable live code updates without needing to rebuild or re-save the HDA.
</p>

<h2>Features</h2>
<ul>
  <li><strong>Live Code Reloading</strong> — Dynamically purges cached Python modules (<code>sys.modules</code>) during execution, allowing developers to push Python updates instantly without restarting Houdini sessions.</li>
  <li><strong>Deadline Integration</strong> — Direct callback submission to AWS Thinkbox Deadline for network rendering and flipbook management.</li>
  <li><strong>Detailed Error Handling</strong> — Includes full traceback and diagnostic logging to facilitate rapid debugging in the Houdini Python shell/console.</li>
</ul>

<h2>Repository Structure</h2>
<div class="tree">.
├── houdini/
│   └── python/
│       └── houdini_opengl_flipbook/
│           ├── __init__.py
│           ├── main.py
│           └── DL_submit.py
└── README.md</div>

<h2>Environment &amp; Path Setup</h2>
<p>
  Ensure that the environment variable <code>$HDA_SCRIPTS</code> is defined in your pipeline or Houdini environment setup 
  (<code>houdini.env</code> or launcher environment):
</p>

<pre><code># Example environment setting
export HDA_SCRIPTS="/path/to/your/global/scripts"</code></pre>

<p>
  The script expects the package to reside at:
</p>
<pre><code>${HDA_SCRIPTS}/houdini/python/houdini_opengl_flipbook</code></pre>

<div class="note">
  <strong>Tip:</strong> Add the path to your studio’s central scripts repository so all artists share the same live-updating code.
</div>

<h2>HDA Callback Configuration</h2>
<p>
  The HDA utilizes Houdini’s Python Module (<code>hou.phm()</code>) to trigger callbacks for user actions.
</p>

<table>
  <thead>
    <tr>
      <th>Button / Parameter</th>
      <th>Callback Script</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>Update</code></td>
      <td><code>hou.phm().update(kwargs)</code></td>
      <td>Reloads submodules and executes UI parameter updates.</td>
    </tr>
    <tr>
      <td><code>Submit Render to Deadline</code></td>
      <td><code>hou.phm().deadlineSubmitter(kwargs)</code></td>
      <td>Triggers the Deadline submission process.</td>
    </tr>
  </tbody>
</table>

<h2>HDA Python Module (<code>hou.phm()</code>) Code</h2>
<p>
  Copy and paste the following Python script into the <strong>Python Module</strong> tab inside your HDA’s Type Properties:
</p>

<pre><code>import sys
import os
import runpy
import importlib
import traceback

def _reload_and_call(module_name, func_name, kwargs):
    """Purges module cache and executes a target function via runpy."""
    full_module = f"{module_name}.main"
    
    # Module cleanup
    for k in list(sys.modules.keys()):
        if module_name in k:
            print(f"Removing: {k}")
            del sys.modules[k]
    
    module = runpy.run_module(full_module, run_name="__main__", alter_sys=False)
    func = module[func_name]
    return func(kwargs)

def deadlineSubmitter(kwargs):
    """Callback for the 'Submit Render to Deadline' button."""
    module_path = os.path.expandvars('$HDA_SCRIPTS/houdini/python')
    if module_path not in sys.path:
        sys.path.append(module_path)
    import houdini_opengl_flipbook
    importlib.reload(houdini_opengl_flipbook)
    
    return houdini_opengl_flipbook.DL_submit.deadlineSubmitter(kwargs)

def update(kwargs):
    """Callback for the 'Update' button."""
    module_path = os.path.expandvars('$HDA_SCRIPTS/houdini/python')
    if module_path not in sys.path:
        sys.path.append(module_path)
    module_name = "houdini_opengl_flipbook"
    for k in list(sys.modules.copy().keys()):
        if module_name in k:
            del sys.modules[k]
  
    try:
        from houdini_opengl_flipbook import DL_submit
        importlib.reload(DL_submit)
        DL_submit.update(kwargs)            
    except Exception as e:
        print("=" * 90)
        print("ERROR: Failed to execute update")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {e}")
        traceback.print_exc()
        print("=" * 90)</code></pre>

<div class="note">
  <strong>Note:</strong> The original snippet was truncated. The <code>except</code> block above has been completed with standard traceback printing so the module is immediately usable.
</div>

<h2>Usage</h2>
<ol>
  <li>Place the Python package under <code>$HDA_SCRIPTS/houdini/python/houdini_opengl_flipbook</code>.</li>
  <li>Create or open your HDA and paste the Python Module code into the Type Properties → Scripts → Python Module tab.</li>
  <li>Wire the <strong>Update</strong> and <strong>Submit Render to Deadline</strong> buttons to the corresponding callbacks shown in the table above.</li>
  <li>Press <strong>Update</strong> to reload the external scripts and refresh parameters.</li>
  <li>Press <strong>Submit Render to Deadline</strong> to send the OpenGL flipbook job to the farm.</li>
</ol>

<h2>Requirements</h2>
<ul>
  <li>SideFX Houdini (Python 3.x)</li>
  <li>AWS Thinkbox Deadline (with appropriate Houdini / OpenGL plugins configured)</li>
  <li>Environment variable <code>$HDA_SCRIPTS</code> pointing to your central scripts root</li>
</ul>

<div class="footer">
  Designed for rapid iteration in production pipelines — edit the external Python files and hit Update inside Houdini.
</div>

</div>
</body>
</html>
