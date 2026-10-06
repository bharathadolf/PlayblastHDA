#DL_submit.py
#!/usr/bin/env python3
"""
════════════════════════════════════════════════════════════════════════════════
                    DEADLINE SUBMITTER WITH POST-PROCESSING
                         Integrated Error Suggestion System
════════════════════════════════════════════════════════════════════════════════

This script submits Houdini OpenGL flipbook renders to Deadline with automatic
post-processing. It includes built-in error handling that prints contextual
solutions whenever an error occurs.

FEATURES:
    • Automatic error detection with suggested solutions
    • Shotgun/Toolkit integration for path resolution
    • OpenGL ROP detection and parameter gathering
    • Automatic scene copying to .deadline folder
    • JSON metadata generation for post-processing
    • Deadline job specification builder

USAGE:
    1. Select the subnet node containing the OpenGL ROP
    2. Run: deadlineSubmitter({"node": hou.selectedNodes()[0]})
    3. Or click the "Submit to Deadline" button on the HDA

ERROR HANDLING:
    Whenever an error occurs, the system automatically:
    1. Prints the full traceback
    2. Identifies the error category
    3. Displays 3-5 specific solutions
    4. Indicates severity level (CRITICAL/HIGH/MEDIUM/LOW)

AUTHOR: Achanta.Bharath Babu ( Pipeline TD )
"""

import json
import os
import sys
import math
import getpass
import shutil
import hou
import datetime
import traceback
from typing import Dict, Any, List, Optional, Tuple
from functools import wraps




from .error_system import ErrorSuggestionSystem, with_suggestions
try:
    import sgtk
    eng = sgtk.platform.current_engine()
    PROJECT_NAME = eng.context.project.get("name", "UnknownProject")
    tk = eng.sgtk
    ENGINE = eng
except Exception as e:
    ErrorSuggestionSystem.print_suggestion(e, "Shotgun Pipeline Setup")
    if hou.isUIAvailable():
        hou.ui.displayMessage("Please open the file from Shotgun.", title="Path Error")
    raise RuntimeError("Invalid file path: Shotgun context not found.") from e

HIP_PATH = os.getenv("HIPFILE", "")
DEFAULT_POOL = "fx_cache" if "/fx/" in HIP_PATH.lower() else "lighting_cache"

ALCHEMY_PKG_PATH = "{HDA_SCRIPTS}/python/site-packages"
if ALCHEMY_PKG_PATH not in sys.path:
    sys.path.append(ALCHEMY_PKG_PATH)

try:
    from deadline_api.DeadlineFeatures import DeadlineFeatures
except Exception as e:
    ErrorSuggestionSystem.print_suggestion(e, "Deadline API Import")
    raise



current_dir = os.path.dirname(os.path.abspath(__file__))
POST_SCRIPT_PATH = current_dir + "/post_script.py"
JSON_BASE_DIR = "{HDA_SCRIPTS}/logs/opengl_flipbook_json"


class ParameterValidationError(Exception):
    pass


class HoudiniDeadlineSubmitter:
    def __init__(self):
        self.deadline_api = DeadlineFeatures()
        if not hasattr(self.deadline_api, 'conn') or self.deadline_api.conn is None:
            if hasattr(self.deadline_api, 'Connect'):
                self.deadline_api.Connect()
            elif hasattr(self.deadline_api, 'connect'):
                self.deadline_api.connect()
        self.project_name = PROJECT_NAME
        self.hip_path = HIP_PATH
        self.pool = DEFAULT_POOL
        self.engine = ENGINE
        self.username = getpass.getuser()

    def _get_deadline_connection(self):
        for attr in ['conn', 'connection', 'Connection', '_connection', 'DeadlineConnection']:
            conn = getattr(self.deadline_api, attr, None)
            if conn:
                return conn

        if hasattr(self.deadline_api, 'GetJob'):
            return self.deadline_api
        return None

    def _check_connection(self):
        """Verify Deadline connection is alive."""
        conn = self._get_deadline_connection()
        if not conn:
            return False
        try:
            # Try a lightweight API call
            if hasattr(conn, 'Jobs'):
                conn.Jobs.GetJobIds()  # or GetPools()
            return True
        except Exception as e:
            print(f"Deadline connection test failed: {e}")
            return False

    @with_suggestions
    def _safe_eval_parm(self, node, parm_name, default):
        return (parm := node.parm(parm_name)).eval() if parm else default

    @with_suggestions
    def _find_opengl(self, parent):
        for child in parent.allSubChildren():
            if child.type().name() == "opengl":
                print(f"OpenGl node :{child.type().name()} \nOpenGl path : {child.path()} \n")
                return child
        return None

    def _has_execute_parm(self, node):
        return any(p.name() == "execute" for p in node.allParms())

    @with_suggestions
    def _get_frame_range(self, rop):
        return (int(rop.parm("f1").eval()), int(rop.parm("f2").eval())) if rop.parm("trange").eval() == 1 else (int(hou.frame()), int(hou.frame()))

    def _update_parameters(self, node: hou.Node, param_map: list[tuple[str, any]]):
        for parm_name, value in param_map:
            parm = node.parm(parm_name)
            if parm:
                parm.set(value)
                print(f" ✅ Updated '{parm_name}' → {value}")
            else:
                print(f" ⚠️  Parameter '{parm_name}' not found")

    @with_suggestions
    def _get_camera(self, opengl, hda_node=None):
        resolved_cam = None

        # 1. Try to resolve camera set on the internal OpenGL node first
        if opengl and (cam_parm := opengl.parm("camera")):
            raw_path = cam_parm.eval()
            if raw_path and raw_path.strip():
                if resolved := (opengl.node(raw_path) or hou.node(raw_path)):
                    resolved_cam = resolved.path()

        # 2. Try to resolve camera set on the main HDA node
        if not resolved_cam and hda_node and (hda_cam_parm := hda_node.parm("camera")):
            raw_path = hda_cam_parm.eval()
            if raw_path and raw_path.strip():
                if resolved := (hda_node.node(raw_path) or hou.node(raw_path)):
                    resolved_cam = resolved.path()

        # 3. Fallback: Search /obj level for camera nodes
        if not resolved_cam:
            obj_node = hou.node("/obj")
            cameras = [node for node in obj_node.allSubChildren() if node.type().name() == "cam"] if obj_node else []
            cam_count = len(cameras)

            if cam_count > 0:
                resolved_cam = cameras[0].path()
                if cam_count > 1:
                    print(f"🎥 Found {cam_count} cameras under /obj level. Using first found camera: {resolved_cam}")
                else:
                    print(f"🎥 Found 1 camera under /obj level: {resolved_cam}")
            else:
                print("❌ Camera not found")
                return None

        # 4. Synchronize resolved camera back to both internal OpenGL node & main HDA node
        if resolved_cam:
            if opengl and (cam_parm := opengl.parm("camera")):
                if cam_parm.eval() != resolved_cam:
                    cam_parm.set(resolved_cam)
                    print(f" ✅ Synchronized internal OpenGL ROP 'camera' → {resolved_cam}")

            if hda_node and (hda_cam_parm := hda_node.parm("camera")):
                if hda_cam_parm.eval() != resolved_cam:
                    hda_cam_parm.set(resolved_cam)
                    print(f" ✅ Synchronized HDA node 'camera' → {resolved_cam}")

        return resolved_cam


    @with_suggestions
    def _get_resolution(self, opengl):
        if not opengl or not (override := opengl.parm("tres")).eval():
            return None
        w, h = opengl.parm("res1"), opengl.parm("res2")
        return (int(w.eval()), int(h.eval())) if w and h else None

    @with_suggestions
    def _build_render_output_path(self, rop):
        hip_path = hou.hipFile.path()
        work_template = tk.template_from_path(hip_path)
        if not work_template:
            raise RuntimeError(f"Could not resolve template from: {hip_path}")

        fields = work_template.get_fields(hip_path)
        fields["ext"] = "mov"
        mov_template = tk.templates["houdini_mov_work"]
        mov_path = mov_template.apply_fields(fields)

        mov_dir = os.path.dirname(mov_path)
        mov_basename = os.path.splitext(os.path.basename(mov_path))[0]
        exr_dir_name = f"{mov_basename}_exr"

        exr_filename_houdini = f"{mov_basename}.$F4.exr"
        exr_path_houdini = os.path.join(mov_dir, exr_dir_name, exr_filename_houdini).replace("\\", "/")

        exr_filename_ffmpeg = f"{mov_basename}.%04d.exr"
        exr_path_ffmpeg = os.path.join(mov_dir, exr_dir_name, exr_filename_ffmpeg).replace("\\", "/")

        return mov_path, exr_path_houdini, exr_path_ffmpeg

    @with_suggestions
    def _gather_node_parameters(self, rop):
        params = {
            "node_name": rop.name(),
            "node_path": rop.path(),
            "node_type": rop.type().name(),
            "scene_path": hou.hipFile.path(),
            "project_name": self.project_name,
        }

        start, end = self._get_frame_range(rop)
        params["start_frame"] = start
        params["end_frame"] = end
        params["total_frames"] = end - start + 1

        opengl = self._find_opengl(rop)
        params["opengl_path"] = opengl.path() if opengl else None

        if opengl:
            #params["camera"] = self._get_camera(opengl)
            params["camera"] = self._get_camera(opengl, hda_node=rop)
            params["resolution"] = self._get_resolution(opengl)
            params["output_driver"] = opengl.path()
        else:
            params["camera"] = None
            params["resolution"] = None
            params["output_driver"] = ""

        mov_path, exr_path_houdini, exr_path_ffmpeg = self._build_render_output_path(rop)
        params["mov_path"] = mov_path
        params["exr_path"] = exr_path_houdini
        params["exr_path_ffmpeg"] = exr_path_ffmpeg

        return params

    @with_suggestions
    def copy_scene_to_deadline_folder(self):
        hip_path = hou.hipFile.path()
        hip_dir = os.path.dirname(hip_path)
        lower = hip_path.lower()

        # FIX 1: Added proper if-block indentation. The raise was executing unconditionally.
        if "/publish/" in lower or "/ref/" in lower:
            msg = "Please open the file from your workspace."
            (hou.ui.displayMessage(msg, title="Path Error") if hou.isUIAvailable() else print(f"ERROR: {msg}"))
            raise RuntimeError("Cannot submit from publish/ref path.")

        deadline_dir = os.path.join(hip_dir, ".deadline")
        new_path = os.path.join(deadline_dir, os.path.basename(hip_path))
        os.makedirs(deadline_dir, exist_ok=True)

        app = self.engine.apps["tk-houdini-alembicnode"]

        try:
            app.convert_to_regular_alembic_nodes()
            hou.hipFile.save()
            shutil.copy2(hip_path, new_path)
            app.convert_back_to_tk_alembic_nodes()
            hou.hipFile.save(file_name=hip_path)
        except Exception as e:
            ErrorSuggestionSystem.print_suggestion(e, "Scene Copy Operation")
            if hasattr(app, 'convert_back_to_tk_alembic_nodes'):
                app.convert_back_to_tk_alembic_nodes()
                hou.hipFile.save()
            raise RuntimeError(f"Scene copy failed: {e}")

        return new_path

    @with_suggestions
    def _write_json_metadata(self, params):
        now = datetime.datetime.now()
        date_folder = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%Y-%m-%d-%H:%M:%S")

        json_dir = os.path.join(JSON_BASE_DIR, date_folder)
        os.makedirs(json_dir, exist_ok=True)

        json_filename = f"opengl_flipbook_{self.username}_{timestamp}.json"
        json_path = os.path.join(json_dir, json_filename)

        json_data = {
            "Exr_Path": params["exr_path_ffmpeg"],
            "Mov_Path": params["mov_path"],
            "Frame_In": params["start_frame"],
            "Frame_Out": params["end_frame"],
            "Contactsheet_Frame_Out": params["end_frame"],
            "Shot_Width": params["resolution"][0] if params.get("resolution") else None,
            "Shot_Height": params["resolution"][1] if params.get("resolution") else None,
            "Project_Width": 1920,
            "Project_Height": 1080,
            "layers_for_contact_sheet": [],
            "Submitted_By": self.username,
            "Submit_Time": timestamp
        }

        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)

        print(f" ✅ JSON metadata saved: {json_path}")
        return json_path

    @with_suggestions
    def _build_job_spec(self, rop):
        deadline_scene = self.copy_scene_to_deadline_folder()
        params = self._gather_node_parameters(rop)

        is_valid, errors = self.validate_parameters(params)
        if not is_valid:
            raise ParameterValidationError(f"Validation failed: {errors}")

        json_path = self._write_json_metadata(params)

        filename_base = (
            f"{self.project_name.upper()}_"
            f"{os.path.splitext(os.path.basename(deadline_scene))[0]}"
        )

        start = params["start_frame"]
        end = params["end_frame"]

        chunk = 1

        ocio = (
            "{HDA_SCRIPTS}/OCIOConfigs/configs/aces_1.2/config.ocio"
            if "oss" in deadline_scene.lower()
            else "{HDA_SCRIPTS}/OCIOConfigs/configs/default/studio-config-v1.0.0_aces-v1.3_ocio-v2.1.ocio"
        )

        output_driver = params.get("output_driver", "")
        hou_version = hou.applicationVersionString()
        houdini_path = f"/opt/hfs{hou_version}"

        # provides virtual display environment required for opengl Qt init
        xvfb_bin = "/usr/bin/xvfb-run"

        command = f"cd {houdini_path}; source ./houdini_setup; {xvfb_bin} -a {houdini_path}/bin/hrender -e -f <STARTFRAME> <ENDFRAME> -d {output_driver} \"{deadline_scene}\""

        job_info = {
            "Name": f"{rop.name()} - Hip to Playblast",
            "BatchName": filename_base,
            "Plugin": "CommandLine",
            "Priority": 75,
            "Pool": self.pool,
            "SecondaryPool": self.pool,
            "Frames": f"{start}-{end}",
            "ChunkSize": chunk,
            "UserName": self.username,
            "PostJobScript": POST_SCRIPT_PATH,
            "EnvironmentKeyValue0": f"OCIO={ocio}",
            "EnvironmentKeyValue1": "HOUDINI_PACKAGE_DIR={HDA_SCRIPTS}/houdini/packages",
        }

        plugin_info = {
            "Shell": "sh",
            "ShellExecute": "True",
            "JSON_PATH": json_path,
            "Arguments": command,
        }

        spec = {
            "JobInfo": job_info,
            "PluginInfo": plugin_info,
            "AuxiliaryFiles": [json_path],
        }

        print(
            "\n"
            + "=" * 80
            + f"\nJOB SPEC - {rop.path()}\n"
            + "=" * 80
            + f"\n{json.dumps(spec, indent=2)}\n"
            + "=" * 80
            + "\n"
        )

        return spec

    def validate_parameters(self, params):
        errors = [
            msg for msg, cond in [
                ("Scene has unsaved changes", hou.hipFile.hasUnsavedChanges()),
                ("No OpenGL node found", not params.get("opengl_path")),
                ("No camera specified", not params.get("camera"))
            ] if cond
        ]

        return (len(errors) == 0), errors

    @with_suggestions
    def poll_job_status(self, job_id, interval=5, timeout=None, callback=None):
        import time

        # ── ROBUST CONNECTION RESOLUTION ─────────────────────────────────
        conn = None
        for attr in ['conn', 'connection', 'Connection', '_connection']:
            candidate = getattr(self.deadline_api, attr, None)
            if candidate:
                conn = candidate
                break

        # If no .conn attribute, maybe deadline_api IS the connection wrapper
        if not conn and hasattr(self.deadline_api, 'Jobs'):
            conn = self.deadline_api

        if not conn:
            print("❌ No Deadline connection found. Check DeadlineFeatures initialization.")
            return None

        # Resolve Jobs API (could be conn.Jobs or conn.jobs)
        jobs_api = getattr(conn, 'Jobs', None) or getattr(conn, 'jobs', None)
        if not jobs_api:
            print("❌ Jobs API not found on connection")
            return None

        # ── POLLING SETUP ────────────────────────────────────────────────
        STATUS_MAP = {
            0: ("⏳", "Unknown"),
            1: ("🟢", "Active (Queued/Rendering)"),
            2: ("🟡", "Suspended"),
            3: ("✅", "Completed"),
            4: ("❌", "Failed"),
            5: ("⏸️", "Pending"),
        }
        TERMINAL_STATES = {3, 4}

        print(f"\n{'='*70}")
        print(f"  LIVE MONITORING: Job {job_id}")
        print(f"  Poll interval: {interval}s | Timeout: {timeout or 'None'}")
        print(f"{'='*70}\n")

        start_time = time.time()
        poll_count = 0
        final_data = None

        while True:
            poll_count += 1
            elapsed = int(time.time() - start_time)

            try:
                # ── FETCH JOB DATA ─────────────────────────────────────
                job = jobs_api.GetJob(job_id)

                if not job or not isinstance(job, dict):
                    print(f"⚠️  Poll #{poll_count}: Invalid response (type: {type(job).__name__})")
                    time.sleep(interval)
                    continue

                props = job.get('Props', {})
                stat_code = job.get('Stat', 0)
                icon, status_text = STATUS_MAP.get(stat_code, ("❓", f"Unknown ({stat_code})"))

                # ── BUILD PROGRESS DATA ────────────────────────────────
                data = {
                    'poll': poll_count,
                    'elapsed': elapsed,
                    'job_id': job_id,
                    'name': props.get('Name', 'N/A'),
                    'status_code': stat_code,
                    'status': status_text,
                    'icon': icon,
                    'progress': job.get('SnglTskPrg', 'N/A'),
                    'completed_chunks': job.get('CompletedChunks', 0),
                    'queued_chunks': job.get('QueuedChunks', 0),
                    'rendering_chunks': job.get('RenderingChunks', 0),
                    'suspended_chunks': job.get('SuspendedChunks', 0),
                    'failed_chunks': job.get('FailedChunks', 0),
                    'pending_chunks': job.get('PendingChunks', 0),
                    'total_tasks': props.get('Tasks', 0),
                    'frames': props.get('Frames', 'N/A'),
                    'machine': job.get('Mach', 'N/A'),
                    'errors': job.get('Errs', 0),
                    'plugin': job.get('Plug', 'N/A'),
                    'pool': props.get('Pool', 'N/A'),
                    'priority': props.get('Pri', 'N/A'),
                    'user': props.get('User', 'N/A'),
                }

                # Calculate percentage
                total = (data['completed_chunks'] + data['queued_chunks'] +
                        data['rendering_chunks'] + data['suspended_chunks'] +
                        data['failed_chunks'] + data['pending_chunks'])
                data['percent'] = (data['completed_chunks'] / total * 100) if total > 0 else 0

                # ── PRINT LIVE UPDATE ──────────────────────────────────
                print(f"{icon} [{elapsed:>5}s] Poll #{poll_count:>3} | "
                      f"{data['name'][:40]:<40} | {status_text:<20} | "
                      f"Progress: {data['progress']:<6} | "
                      f"Done:{data['completed_chunks']:>2}/{total:<2} | "
                      f"Err:{data['errors']:>2}")

                if total > 0:
                    bar_len = 30
                    filled = int(bar_len * data['percent'] / 100)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    print(f"   └─ [{bar}] {data['percent']:.1f}%  "
                          f"(Rendering:{data['rendering_chunks']} "
                          f"Queued:{data['queued_chunks']} "
                          f"Failed:{data['failed_chunks']})")

                # ── CALLBACK & TERMINAL CHECK ──────────────────────────
                if callback:
                    callback(data)

                final_data = data

                if stat_code in TERMINAL_STATES:
                    print(f"\n{'='*70}")
                    print(f"  JOB FINISHED: {status_text}")
                    print(f"  Total time: {elapsed}s | Polls: {poll_count}")
                    print(f"{'='*70}")
                    return final_data

                # ── TIMEOUT CHECK ──────────────────────────────────────
                if timeout and elapsed >= timeout:
                    print(f"\n⏰ Timeout reached after {timeout}s")
                    return final_data

                time.sleep(interval)

            except Exception as e:
                print(f"❌ Poll #{poll_count} error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(interval)

    @with_suggestions
    def get_job_tasks_detailed(self, job_id):
        conn = None
        for attr in ['conn', 'connection', 'Connection', '_connection']:
            candidate = getattr(self.deadline_api, attr, None)
            if candidate:
                conn = candidate
                break

        if not conn and hasattr(self.deadline_api, 'Tasks'):
            conn = self.deadline_api

        if not conn:
            print("❌ No Deadline connection found")
            return []

        tasks_api = getattr(conn, 'Tasks', None) or getattr(conn, 'tasks', None)
        if not tasks_api:
            print("❌ Tasks API not available")
            return []

        try:
            tasks = tasks_api.GetJobTasks(job_id)
            if not tasks:
                return []

            task_list = []
            if isinstance(tasks, dict) and 'TaskCollectionAllTasks' in tasks:
                for task in tasks['TaskCollectionAllTasks']:
                    task_list.append({
                        'id': task.get('TaskId', 'N/A'),
                        'status': task.get('TaskStatus', 'N/A'),
                        'progress': task.get('TaskProgress', 'N/A'),
                        'errors': task.get('TaskErrorCount', 0),
                        'frame': task.get('TaskFrameString', 'N/A'),
                        'machine': task.get('TaskSlave', 'N/A'),
                    })
            elif isinstance(tasks, list):
                for task in tasks:
                    task_list.append({
                        'id': task.get('TaskId', task.get('_id', 'N/A')),
                        'status': task.get('TaskStatus', task.get('Stat', 'N/A')),
                        'progress': task.get('TaskProgress', 'N/A'),
                        'errors': task.get('TaskErrorCount', 0),
                        'frame': task.get('TaskFrameString', 'N/A'),
                        'machine': task.get('TaskSlave', 'N/A'),
                    })
            return task_list

        except Exception as e:
            print(f"❌ Error fetching tasks: {e}")
            return []

    def print_job_report(self, job_id, max_errors=5):
        print(f"\n{'='*70}")
        print(f"  JOB REPORT: {job_id}")
        print(f"{'='*70}")

        # Robust connection resolution
        conn = None
        for attr in ['conn', 'connection', 'Connection', '_connection']:
            candidate = getattr(self.deadline_api, attr, None)
            if candidate:
                conn = candidate
                break

        if not conn and hasattr(self.deadline_api, 'Jobs'):
            conn = self.deadline_api

        if not conn:
            print("❌ No connection")
            return

        jobs_api = getattr(conn, 'Jobs', None) or getattr(conn, 'jobs', None)
        if not jobs_api:
            print("❌ Jobs API not found")
            return

        try:
            job = jobs_api.GetJob(job_id)
        except Exception as e:
            print(f"❌ Failed to fetch job: {e}")
            return

        if not job or not isinstance(job, dict):
            print("❌ Job not found or invalid response")
            return

        props = job.get('Props', {})

        print(f"\n📋 JOB INFO")
        print(f"   Name:     {props.get('Name', 'N/A')}")
        print(f"   Batch:    {props.get('Batch', 'N/A')}")
        print(f"   User:     {props.get('User', 'N/A')}")
        print(f"   Plugin:   {job.get('Plug', 'N/A')}")
        print(f"   Pool:     {props.get('Pool', 'N/A')}")
        print(f"   Priority: {props.get('Pri', 'N/A')}")
        print(f"   Frames:   {props.get('Frames', 'N/A')}")
        print(f"   Chunk:    {props.get('Chunk', 'N/A')}")

        print(f"\n📊 STATUS BREAKDOWN")
        print(f"   Completed:  {job.get('CompletedChunks', 0)}")
        print(f"   Rendering:  {job.get('RenderingChunks', 0)}")
        print(f"   Queued:     {job.get('QueuedChunks', 0)}")
        print(f"   Suspended:  {job.get('SuspendedChunks', 0)}")
        print(f"   Failed:     {job.get('FailedChunks', 0)}")
        print(f"   Pending:    {job.get('PendingChunks', 0)}")
        print(f"   Errors:     {job.get('Errs', 0)}")

        tasks = self.get_job_tasks_detailed(job_id)
        if tasks:
            print(f"\n📝 TASKS ({len(tasks)} total)")
            for t in tasks[:20]:
                status_icon = "✅" if t['status'] == 'Completed' else "❌" if t['status'] == 'Failed' else "⏳"
                print(f"   {status_icon} Task {t['id']}: {t['status']:<12} | "
                      f"Frame: {t['frame']:<8} | Progress: {t['progress']:<6} | "
                      f"Machine: {t['machine']}")
            if len(tasks) > 20:
                print(f"   ... and {len(tasks) - 20} more tasks")

        # Error reports
        reports_api = getattr(conn, 'JobReports', None) or getattr(conn, 'job_reports', None)
        if reports_api and hasattr(reports_api, 'GetJobErrorReports'):
            try:
                reports = reports_api.GetJobErrorReports(job_id)
                if reports:
                    print(f"\n❌ ERROR REPORTS")
                    for i, report in enumerate(reports[:max_errors]):
                        msg = report.get('ReportMessage', 'N/A') if isinstance(report, dict) else str(report)
                        print(f"   {i+1}. {msg[:100]}")
            except Exception as e:
                print(f"\n⚠️  Could not fetch error reports: {e}")

        print(f"\n{'='*70}")

    @with_suggestions
    def _print_job_details(self, job_id):
        print(f"   → Fetching job details for ID: {job_id}")

        # Status code mapping for human-readable output
        STATUS_MAP = {
            0: "Unknown",
            1: "Active (Queued/Rendering)",
            2: "Suspended",
            3: "Completed",
            4: "Failed",
            5: "Pending",
        }

        try:
            # ── PRIMARY: DeadlineCon.Jobs.GetJob via deadline_api.conn ──────
            conn = getattr(self.deadline_api, 'conn', None)

            if conn and hasattr(conn, 'Jobs'):
                jobs_api = conn.Jobs

                try:
                    job = jobs_api.GetJob(job_id)

                    if job and isinstance(job, dict):
                        # Top-level properties
                        props = job.get('Props', {})

                        # ── Core Job Info ─────────────────────────────────
                        name = props.get('Name', 'N/A')
                        batch = props.get('Batch', 'N/A')
                        user = props.get('User', 'N/A')
                        frames = props.get('Frames', 'N/A')
                        chunk = props.get('Chunk', 'N/A')
                        tasks = props.get('Tasks', 'N/A')

                        # ── Pool & Priority ─────────────────────────────
                        pool = props.get('Pool', 'N/A')
                        sec_pool = props.get('SecPool', 'N/A')
                        priority = props.get('Pri', 'N/A')
                        group = props.get('Grp', 'N/A')

                        # ── Status ──────────────────────────────────────
                        stat_code = job.get('Stat', 0)
                        status = STATUS_MAP.get(stat_code, f"Unknown ({stat_code})")

                        # ── Progress ─────────────────────────────────────
                        completed = job.get('CompletedChunks', 0)
                        queued = job.get('QueuedChunks', 0)
                        rendering = job.get('RenderingChunks', 0)
                        suspended = job.get('SuspendedChunks', 0)
                        failed = job.get('FailedChunks', 0)
                        pending = job.get('PendingChunks', 0)
                        progress = job.get('SnglTskPrg', 'N/A')
                        errors = job.get('Errs', 0)

                        # ── Plugin & Machine ────────────────────────────
                        plugin = job.get('Plug', 'N/A')
                        machine = job.get('Mach', 'N/A')

                        # ── Dates ───────────────────────────────────────
                        submit_date = job.get('Date', 'N/A')
                        start_date = job.get('DateStart', 'N/A')
                        comp_date = job.get('DateComp', 'N/A')

                        # ── Output ──────────────────────────────────────
                        out_dirs = job.get('OutDir', [])
                        out_files = job.get('OutFile', [])

                        # ── Print formatted output ──────────────────────
                        print(f"   → Job Name    : {name}")
                        print(f"   → Batch Name  : {batch}")
                        print(f"   → Status      : {status}")
                        print(f"   → User        : {user}")
                        print(f"   → Frames      : {frames}")
                        print(f"   → Chunk Size  : {chunk}")
                        print(f"   → Tasks       : {tasks}")
                        print(f"   → Pool        : {pool}")
                        print(f"   → 2nd Pool    : {sec_pool}")
                        print(f"   → Group       : {group}")
                        print(f"   → Priority    : {priority}")
                        print(f"   → Plugin      : {plugin}")
                        print(f"   → Machine     : {machine}")
                        print(f"   → Progress    : {progress}")
                        print(f"   → Chunks: Completed={completed}, Queued={queued}, "
                              f"Rendering={rendering}, Suspended={suspended}, "
                              f"Failed={failed}, Pending={pending}")
                        print(f"   → Errors      : {errors}")
                        print(f"   → Submitted   : {submit_date}")
                        print(f"   → Started     : {start_date}")
                        if comp_date and comp_date != '0001-01-01T00:00:00Z':
                            print(f"   → Completed   : {comp_date}")

                        if out_dirs:
                            print(f"   → Output Dirs : {', '.join(out_dirs)}")
                        if out_files:
                            print(f"   → Output Files: {', '.join(out_files)}")

                        return

                    elif job:
                        print(f"   → GetJob returned non-dict type: {type(job).__name__}")
                        print(f"   → Value: {job}")
                        return

                except Exception as e:
                    print(f"   → GetJob() error: {e}")

                # ── FALLBACK: GetJobDetails (for multiple jobs) ───────────
                try:
                    details = jobs_api.GetJobDetails([job_id])
                    if details:
                        print(f"   → GetJobDetails() result: {details}")
                        return
                except Exception as e:
                    print(f"   → GetJobDetails() error: {e}")

            # ── FALLBACK: DeadlineFeatures wrapper methods ─────────────────
            for method_name in ['GetJob', 'get_job', 'GetJobInfo', 'get_job_info']:
                if hasattr(self.deadline_api, method_name):
                    try:
                        method = getattr(self.deadline_api, method_name)
                        job_info = method(job_id)
                        if job_info:
                            print(f"   → Job Info via {method_name}: {job_info}")
                            return
                    except Exception:
                        continue

            # ── FALLBACK: RepositoryUtils (Scripting API) ────────────────
            try:
                from Deadline.Scripting import RepositoryUtils
                job = RepositoryUtils.GetJob(job_id)
                if job:
                    print(f"   → Job Name : {job.JobName}")
                    print(f"   → Status   : {job.JobStatus}")
                    print(f"   → Pool     : {job.JobPool}")
                    print(f"   → Frames   : {job.JobFrames}")
                    return
            except ImportError:
                pass

            # ── GRACEFUL DEGRADATION ──────────────────────────────────────
            print("   → Job submitted. Detailed info not available via current API wrapper.")
            print(f"   → Check Deadline Monitor for job: {job_id}")

        except Exception as e:
            print(f"   → Could not fetch full job details: {e}")
            print(f"   → Job is submitted successfully. Check Deadline Monitor for: {job_id}")

    @with_suggestions
    def submit_selected_node(self, selected_nodes):
        print("\n" + "=" * 90 + "\n" + " " * 30 + "SENDING TO DEADLINE\n" + "=" * 90)
        all_job_ids = []

        for node in selected_nodes:
            if not self._has_execute_parm(node):
                print(f"⚠️ Skipping {node.name()} - No execute parameter.")
                continue

            print(f"Submitting: {node.path()}")

            try:
                job_spec = self._build_job_spec(node)
            except Exception as e:
                ErrorSuggestionSystem.print_suggestion(e, f"Building Job Spec for {node.path()}")
                continue

            # FIX 3: Defensive check — do not submit if job_spec is None
            if job_spec is None:
                print(f"⚠️ Job spec is None for {node.path()}, skipping submission.")
                continue

            print("-" * 10)
            print(job_spec)
            print("-" * 10)

            try:
                result = self.deadline_api.submitFromJobInfo(job_spec)
                job_id = str(result["_id"]) if isinstance(result, dict) and "_id" in result else (str(result[0]) if isinstance(result, list) and result else str(result))
                all_job_ids.append(job_id)
                print(f"✅ Job Submitted Successfully! Job ID: {job_id}")

                # Print initial details
                self._print_job_details(job_id)

            except Exception as e:
                ErrorSuggestionSystem.print_suggestion(e, f"Submitting {node.name()} to Deadline")

        if all_job_ids:
            msg = f"Successfully sent {len(all_job_ids)} job(s) to Deadline!"
            (
                hou.ui.displayMessage(msg, title="✅ Submission Complete", details="".join(all_job_ids), details_expanded=True)
                if hou.isUIAvailable() else print(f"✅ {msg}\nJob IDs: {''.join(all_job_ids)}")
            )
        else:
            msg = "No jobs were submitted."
            (hou.ui.displayMessage(msg, title="Submission Failed") if hou.isUIAvailable() else print(f"❌ {msg}"))

        return all_job_ids



def deadlineSubmitter(kwargs):
    try:
        submitter = HoudiniDeadlineSubmitter()
        
        # ── RESOLVE TARGET NODES ──────────────────────────────────────────────
        # 1. Get the node that triggered the callback (button click)
        node_from_kwargs = kwargs.get("node") if isinstance(kwargs, dict) else None
        
        # 2. Get currently selected nodes in Network Editor
        selected_nodes = hou.selectedNodes()

        # Selection logic:
        # • If multiple nodes are selected AND the current node is part of selection -> submit all selected
        # • Otherwise -> submit the specific node where the button was clicked
        if selected_nodes and node_from_kwargs in selected_nodes:
            nodes_to_submit = selected_nodes
        elif node_from_kwargs:
            nodes_to_submit = [node_from_kwargs]
        else:
            nodes_to_submit = selected_nodes

        if not nodes_to_submit:
            msg = "No nodes found for submission."
            print(f"⚠️ {msg}")
            if hou.isUIAvailable():
                hou.ui.displayMessage(msg, title="⚠️ Submission Skipped", severity=hou.severityType.Warning)
            return []

        # ── SUBMIT RESOLVED NODES ─────────────────────────────────────────────
        return submitter.submit_selected_node(nodes_to_submit)
    except Exception as e:
        # Catch any initialization errors and print them clearly
        error_msg = f"Failed to execute deadlineSubmitter:\n\n{type(e).__name__}: {e}"
        print(error_msg)
        if hou.isUIAvailable():
            hou.ui.displayMessage(error_msg, title="❌ Submission Failed", severity=hou.severityType.Error)
        raise


@with_suggestions
def update(kwargs: Dict[str, Any]) -> None:
    print("\n" + "=" * 90 + "\n" + " " * 35 + "UPDATING NODE PARAMETERS\n" + "=" * 90)

    try:
        node = kwargs.get("node")
        if not node:
            print("❌ ERROR: No node found in kwargs\n💡 SOLUTION: Verify callback is attached to a valid node")
            return

        print(f"📁 Node: {node.path()}\n📝 Type: {node.type().name()}\n")

        submitter = HoudiniDeadlineSubmitter()
        start_frame = end_frame = resolution = None
        exr_path_houdini = mov_path = None
        camera_path = None

        # -------------------------------------------------------------
        # 0. LOCATE OPENGL ROP
        # -------------------------------------------------------------
        rop_node = submitter._find_opengl(node)
        if not rop_node:
            print(f"❌ No OpenGL ROP found under {node.path()}\n💡 SOLUTION: Create an OpenGL ROP inside this subnet")
            return

        print(f"✓ Found OpenGL node: {rop_node.path()}")

        # 1. UPDATE CAMERA & BACKGROUND IMAGE
        print(f"\n{'-' * 40}\n🎥 UPDATING CAMERA...\n{'-' * 40}")

        camera_path = submitter._get_camera(rop_node)
        camera_parm = node.parm("camera")

        if camera_path and camera_parm:
            camera_parm.set(str(camera_path))
            print(f"   ✅ Updated 'camera' to: {camera_path}")
        else:
            print("   ⚠️ Camera not found or 'camera' parameter missing on HDA")

        # Resolve Camera Node (supports both absolute and relative paths)
        cam_node = None
        if rop_node.parm("camera"):
            cam_node = rop_node.parm("camera").evalAsNode()
        
        if not cam_node and camera_path:
            cam_node = rop_node.node(str(camera_path)) or hou.node(str(camera_path))

        #print(f" cam_node : {cam_node}")

        if cam_node:
            vm_bg_parm = cam_node.parm("vm_background")
            print(f" vm_bg_parm : {vm_bg_parm.eval() if vm_bg_parm else None}")
            bgimage_parm = node.parm("bgimage")
            print(f" bgimage_parm : {bgimage_parm.eval() if bgimage_parm else None}")

            if vm_bg_parm and bgimage_parm:
                bg_val = vm_bg_parm.evalAsString()
                raw_bg_path = vm_bg_parm.unexpandedString()

                bgimage_parm.set(raw_bg_path)

                print(f"⚠️ Raw Path with Variables: {raw_bg_path}")
                print(f"✅ Updated 'bgimage' raw value to: {bgimage_parm.unexpandedString()}")
                print(f"✅ Resolved absolute path: {bgimage_parm.eval()}")

            elif not vm_bg_parm:
                print(f"   ℹ️ Parameter 'vm_background' not found on camera: {cam_node.path()}")
            elif not bgimage_parm:
                print(f"   ℹ️ Parameter 'bgimage' not found on HDA node: {node.path()}")
        elif camera_path:
            print(f"   ⚠️ Camera node at '{camera_path}' could not be resolved in the scene")


        # 2. UPDATE OUTPUT IMAGE PATH (EXR & MOV)
        print(f"\n{'-' * 40}\n📁 UPDATING OUTPUT IMAGE PATH...\n{'-' * 40}")

        if submitter._has_execute_parm(rop_node):
            try:
                mov_path, exr_path_houdini, _ = submitter._build_render_output_path(rop_node)
                print(f"✓ Generated EXR path (Houdini): {exr_path_houdini}")
                print(f"✓ Generated MOV path: {mov_path}")
            except Exception as e:
                ErrorSuggestionSystem.print_suggestion(e, "Building Output Path")

        if exr_path_houdini:
            if picture_parm := node.parm("picture"):
                picture_parm.set(exr_path_houdini)
                print(f"   ✅ Updated 'picture' to: {exr_path_houdini}")
            else:
                print(f"   ⚠️ Parameter 'picture' not found on node {node.path()}")

        if mov_path:
            if mov_parm := node.parm("mov_path"):
                mov_parm.set(mov_path)
                print(f"   ✅ Updated 'mov_path' to: {mov_path}")
            else:
                print(f"   ⚠️ Parameter 'mov_path' not found on node {node.path()}")

        # 3. UPDATE FRAME RANGE & RESOLUTION
        print(f"\n{'-' * 40}\n📁 ℹ️ UPDATING ADDITIONAL PARAMETERS...\n{'-' * 40}")

        # Frame Range
        try:
            start, end = submitter._get_frame_range(rop_node)
            submitter._update_parameters(node, [("f1", start), ("f2", end)])
            print("   ✅ FRAME RANGE UPDATED SUCCESSFULLY")
            start_frame, end_frame = start, end
        except Exception as e:
            ErrorSuggestionSystem.print_suggestion(e, "Updating Frame Range")

        # Resolution
        try:
            resolution = submitter._get_resolution(rop_node)
            if resolution:
                submitter._update_parameters(node, [("res1", resolution[0]), ("res2", resolution[1])])
                print("   ✅ RESOLUTION UPDATED SUCCESSFULLY")
            else:
                print("   ℹ️ Resolution override not enabled on OpenGL node")
        except Exception as e:
            ErrorSuggestionSystem.print_suggestion(e, "Updating Resolution")

        # 4. SUMMARY & UI DISPLAY
        print("\n" + "=" * 90 + "\n" + " " * 35 + "UPDATE COMPLETE\n" + "=" * 90)

        cam_display = camera_path or "N/A"
        exr_display = exr_path_houdini or "N/A"
        mov_display = mov_path or "N/A"

        if start_frame is not None and end_frame is not None:
            try:
                frame_count = int(end_frame) - int(start_frame) + 1
                frame_range_str = f"{start_frame} → {end_frame} ({frame_count} frames)"
            except (TypeError, ValueError, AttributeError):
                frame_range_str = f"{start_frame} → {end_frame}"
        else:
            frame_range_str = "N/A"

        res_str = f"{resolution[0]} × {resolution[1]}" if resolution else "N/A"

        summary = (
            "🟢 UPDATE SUCCESSFUL\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Node: {node.path()}\n"
            f"🔗 ROP Source: {rop_node.path()}\n\n"
            f"🎥 Camera: {cam_display}\n"
            f"📁 EXR Path: {exr_display}\n"
            f"🎬 MOV Path: {mov_display}\n\n"
            f"🎞  Frame Range: {frame_range_str}\n"
            f"🖼  Resolution: {res_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ All parameters synchronized successfully."
        )
        print(summary)

        if hou.isUIAvailable():
            trunc = lambda s, l=140: f"...{s[-l:]}" if len(s) > l and s != "N/A" else s
            ui_msg = (
                f"Node: {node.name()}\n"
                f"ROP: {rop_node.name()}\n\n"
                f"Camera: {cam_display}\n"
                f"EXR: {trunc(exr_display)}\n"
                f"MOV: {trunc(mov_display)}\n\n"
                f"Frames: {frame_range_str}\n"
                f"Resolution: {res_str}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "All parameters synchronized."
            )
            hou.ui.displayMessage(ui_msg, title="🟢 UPDATE SUCCESSFUL", severity=hou.severityType.Message)

    except Exception as e:
        ErrorSuggestionSystem.print_suggestion(e, "Update Callback")
        error_msg = f"Update failed:\n\n{type(e).__name__}: {e}"
        if hou.isUIAvailable():
            hou.ui.displayMessage(error_msg, title="❌ UPDATE FAILED", severity=hou.severityType.Error)
        else:
            print(f"\n❌ {error_msg}")
