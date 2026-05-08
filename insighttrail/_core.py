import json
import os
import traceback
from datetime import datetime
from importlib.metadata import distributions

import requests


def load_required_packages(start_path):
    current_path = start_path
    for _ in range(5):
        requirements_file = os.path.join(current_path, "requirements.txt")
        if os.path.exists(requirements_file):
            try:
                with open(requirements_file, "r") as f:
                    packages = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            package_name = line.split("#")[0].strip()
                            package_name = (
                                package_name.split("==")[0]
                                .split(">=")[0]
                                .split("<=")[0]
                                .split("~=")[0]
                                .split("<")[0]
                                .split(">")[0]
                                .split("!=")[0]
                                .strip()
                            )
                            if package_name:
                                packages.append(package_name.lower())
                    return packages
            except IOError:
                return []

        parent = os.path.dirname(current_path)
        if parent == current_path:
            break
        current_path = parent

    return []


def get_package_info(required_packages):
    packages = []
    insighttrail_deps = {"flask", "waitress", "psutil", "requests", "fastapi", "starlette"}
    app_deps = set(required_packages)
    required_set = app_deps.union(insighttrail_deps)

    for dist in distributions():
        try:
            name = dist.metadata["Name"]
            package_key = name.lower()

            package = {
                "name": package_key,
                "current_version": dist.version,
                "latest_version": dist.version,
                "required": package_key in required_set,
                "description": dist.metadata.get("Summary"),
            }

            try:
                pypi_url = f"https://pypi.org/pypi/{package_key}/json"
                response = requests.get(pypi_url, timeout=2)
                if response.status_code == 200:
                    pypi_data = response.json()
                    package["latest_version"] = pypi_data["info"]["version"]
                    if not package["description"]:
                        package["description"] = pypi_data["info"]["summary"]
            except (requests.RequestException, KeyError, ValueError):
                pass

            packages.append(package)
        except Exception:
            continue

    return sorted(packages, key=lambda x: (not x["required"], x["name"].lower()))


def _serialize_logs(logs):
    for log in logs:
        if isinstance(log.get("request_time"), datetime):
            log["request_time"] = log["request_time"].isoformat()
    return logs


def parse_log_file(log_file):
    logs = []
    try:
        with open(log_file, "r") as f:
            for line in f:
                try:
                    log_entry = json.loads(line)
                    log_entry["request_time"] = datetime.strptime(
                        log_entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"
                    )
                    logs.append(log_entry)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        logs.sort(key=lambda log: log["request_time"], reverse=True)
        return _serialize_logs(logs)
    except Exception:
        return []


def get_code_context(filename, line_number, context_lines=5):
    try:
        if not os.path.exists(filename):
            return None

        with open(filename, "r", encoding="utf-8") as file:
            lines = file.readlines()

        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        return {
            "lines": [line.rstrip("\n") for line in lines[start:end]],
            "start_line": start + 1,
            "error_line": line_number,
            "filename": filename,
        }
    except Exception:
        return None


def build_error_info(error, request_info=None):
    frames = []
    tb = error.__traceback__

    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        function = tb.tb_frame.f_code.co_name
        line_number = tb.tb_lineno

        context = get_code_context(filename, line_number)

        local_vars = {}
        for key, value in tb.tb_frame.f_locals.items():
            if not key.startswith("__") and not callable(value):
                try:
                    local_vars[key] = str(value)
                except Exception:
                    local_vars[key] = f"<{type(value).__name__}>"

        frame_info = {
            "filename": filename,
            "function": function,
            "line": line_number,
            "context": context,
            "locals": local_vars,
        }
        frames.append(frame_info)
        tb = tb.tb_next

    error_info = {
        "type": error.__class__.__name__,
        "message": str(error),
        "frames": frames,
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        "context": {
            "module": getattr(error, "__module__", "unknown"),
            "doc": getattr(error, "__doc__", None),
            "args": getattr(error, "args", None),
        },
    }

    if request_info:
        error_info["context"].update(request_info)

    return error_info
