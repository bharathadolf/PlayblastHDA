#main.py
#!/usr/bin/env python3

import sys, os
import hou
from functools import wraps

module_path ='{HDA_SCRIPTS}/houdini/python'
if module_path not in sys.path:
    sys.path.append(module_path)

module_name = "houdini_opengl_flipbook"
module_copy = sys.modules.copy()
for k, v in module_copy.items():
    if module_name in k:
        print(k)
        del sys.modules[k]


import hou
from .DL_submit import HoudiniDeadlineSubmitter
from .error_system import ErrorSuggestionSystem, with_suggestions


@with_suggestions
def deadlineSubmitter(kwargs):
    """
    Submit selected nodes to Deadline.
    Called by the HDA callback via the function_call script.
    """
    import sgtk
    engine = sgtk.platform.current_engine()
    if not engine.context.task:
        hou.ui.displayMessage("Task entry is not available on Shotgrid")
        return

    submitter = HoudiniDeadlineSubmitter()
    return submitter.submit_selected_node(hou.selectedNodes())

#for tool calling
if __name__ == "__main__":
    deadlineSubmitter(kwargs)

#For shelf tool
deadlineSubmitter(kwargs)
