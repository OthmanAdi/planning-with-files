#!/bin/sh
# Qoder CLI invokes this through bash on every supported OS. Probe absolute
# interpreter paths without consuming event JSON or importing project Python.
if [ -z "${QODER_PLUGIN_ROOT:-}" ]; then
    printf '%s\n' '[planning-with-files] QODER_PLUGIN_ROOT is missing.' >&2
    exit 1
fi
try_python() {
    candidate="$1"
    shift
    if "$candidate" "$@" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' </dev/null >/dev/null 2>&1; then
        exec "$candidate" "$@" -I "$QODER_PLUGIN_ROOT/.qoder-plugin/hook_adapter.py"
    fi
}
# A relative or empty PATH component can name code in the current project.
# Git Bash presents Windows PATH entries as absolute POSIX paths here.
saved_ifs="$IFS"
set -f
IFS=:
trusted_path=""
for directory in ${PATH-}; do
    case "$directory" in /*) ;; *) continue ;; esac
    case "$directory" in
        *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) continue ;;
    esac
    trusted_path="${trusted_path:+$trusted_path:}$directory"
done
IFS="$saved_ifs"
PATH="$trusted_path"
export PATH
for interpreter in python3 python py; do
    IFS=:
    for directory in ${PATH-}; do
        case "$directory" in /*) ;; *) continue ;; esac
        case "$directory" in
            *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) continue ;;
        esac
        IFS="$saved_ifs"
        for suffix in '' .exe; do
            candidate="$directory/$interpreter$suffix"
            [ -f "$candidate" ] && [ -x "$candidate" ] || continue
            if [ "$interpreter" = py ]; then
                try_python "$candidate" -3
            else
                try_python "$candidate"
            fi
        done
    done
done
IFS="$saved_ifs"
printf '%s\n' '[planning-with-files] Qoder hooks require Python 3.10 or newer on an absolute PATH entry.' >&2
exit 1
