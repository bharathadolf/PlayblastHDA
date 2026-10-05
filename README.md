Houdini OpenGL Flipbook SubmitterA Houdini Digital Asset (HDA) integration and Python toolset designed to streamline OpenGL flipbook rendering and deadline submission directly within SideFX Houdini.Overview

This repository contains the external Python scripts that drive the Houdini Digital Asset (HDA). 

The asset acts as a lightweight interface, delegating execution and logic to an external module location ($HDA_SCRIPTS) to enable live code updates without needing to rebuild or re-save the HDA.
FeaturesLive Code Reloading: Dynamically purges cached Python modules (sys.modules) during execution, allowing developers to push Python updates instantly without restarting Houdini sessions.
Deadline Integration: Direct callback submission to AWS Thinkbox Deadline for network rendering and flipbook management.
Detailed Error Handling: Includes full traceback and diagnostic logging to facilitate rapid debugging in the Houdini Python shell/console.Repository Structure.

├── houdini/
│   └── python/
│       └── houdini_opengl_flipbook/
│           ├── __init__.py
│           ├── main.py
│           └── DL_submit.py
└── README.md

Environment & Path Setup
Ensure that the environment variable $HDA_SCRIPTS is defined in your pipeline or Houdini environment setup (houdini.env or launcher environment):

# Example environment setting
export HDA_SCRIPTS="/path/to/your/global/scripts"

The script expects the package to reside at: 

${HDA_SCRIPTS}/houdini/python/houdini_opengl_flipbook
HDA Callback ConfigurationThe HDA utilizes Houdini's Python Module (hou.phm()) to trigger callbacks for user actions.
Button / ParameterCallback ScriptDescriptionUpdatehou.phm().update(kwargs)Reloads submodules and executes UI parameter updates.
Submit Render to Deadlinehou.phm().deadlineSubmitter(kwargs)Triggers the Deadline submission process.
HDA Python Module (hou.phm()) CodeCopy and paste the following Python script into the Python Module tab inside your HDA's Type Properties:

```
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
        print(f"Exception Message
```
