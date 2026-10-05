Here is the cleaned, properly formatted `README.md` file:

```markdown
# Houdini OpenGL Flipbook Submitter

A Houdini Digital Asset (HDA) integration and Python toolset designed to streamline OpenGL flipbook rendering and AWS Thinkbox Deadline submission directly within SideFX Houdini.

---

## Overview

This repository contains the external Python scripts that drive the companion Houdini Digital Asset (HDA). 

The asset acts as a lightweight interface, delegating execution and core logic to an external module path (`$HDA_SCRIPTS`). This architecture enables **hot-reloading**—allowing developers to update, test, and push Python code live without needing to rebuild, unlock, or re-save the HDA in active Houdini sessions.

---

## Features

- **Live Code Reloading:** Dynamically flushes cached Python modules from `sys.modules` during execution, allowing developers to push Python updates instantly without restarting Houdini.
- **Deadline Integration:** Direct callback submission to AWS Thinkbox Deadline for distributed network rendering and flipbook management.
- **Robust Error Handling:** Full traceback reporting and diagnostic console logging to facilitate rapid debugging in the Houdini Python shell.

---

## Repository Structure

```text
.
├── houdini/
│   └── python/
│       └── houdini_opengl_flipbook/
│           ├── __init__.py
│           ├── main.py
│           └── DL_submit.py
└── README.md
```

---

## Environment & Path Setup

Ensure that the environment variable `$HDA_SCRIPTS` is defined in your pipeline environment (e.g., your studio launcher, wrapper, or `houdini.env`):

```bash
# Example environment setting
export HDA_SCRIPTS="/path/to/your/global/scripts"
```

The tool expects the package modules to reside at:
```text
${HDA_SCRIPTS}/houdini/python/houdini_opengl_flipbook
```

---

## HDA Configuration

### 1. Parameter Callbacks

Configure your HDA parameter buttons to point to the Python Module (`hou.phm()`):

| Button / Parameter | Callback Script | Description |
| :--- | :--- | :--- |
| **Update** | `hou.phm().update(kwargs)` | Flushes module cache, reloads submodules, and refreshes UI parameters. |
| **Submit Render to Deadline** | `hou.phm().deadlineSubmitter(kwargs)` | Triggers validation and submits the flipbook job to Deadline. |

---

### 2. HDA Python Module (`hou.phm()`)

Copy and paste the following script into the **Scripts > Python Module** tab inside your HDA's **Type Properties**:

```python
import sys
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
        print("=" * 90)
```
```
