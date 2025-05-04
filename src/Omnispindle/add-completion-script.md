mcp --help
MCP is a command line interface for interacting with Model Context Protocol (MCP) servers.
It allows you to discover and call tools, list resources, and interact with MCP-compatible services.

Usage:
  mcp [command]

Available Commands:
  version       Print the version information
  tools         List available tools on the MCP server
  resources     List available resources on the MCP server
  prompts       List available prompts on the MCP server
  call          Call a tool, resource, or prompt on the MCP server
  get-prompt    Get a prompt on the MCP server
  read-resource Read a resource on the MCP server
  shell         Start an interactive shell for MCP commands
  web           Start a web interface for MCP commands
  mock          Create a mock MCP server with tools, prompts, and resources
  proxy         Proxy MCP tool requests to shell scripts
  alias         Manage MCP server aliases
  configs       Manage MCP server configurations
  new           Create a new MCP project component
  guard         Filter tools, prompts, and resources using allow and deny patterns
  help          Help about any command
  completion    Generate the autocompletion script for the specified shell

Flags:
  -f, --format string   Output format (table, json, pretty) (default "table")
  -h, --help            help for mcp
  -p, --params string   JSON string of parameters to pass to the tool (for call command) (default "{}")

Use "mcp [command] --help" for more information about a command.
mcp configs
Manage MCP server configurations including scanning, adding, and aliasing.

Usage:
  mcp configs [command]

Available Commands:
  ls          List all MCP servers in configurations (alias for view --all)
  view        View MCP servers in configurations
  set         Add or update an MCP server configuration
  remove      Remove an MCP server configuration
  alias       Create an alias for a config file
  sync        Synchronize and merge MCP server configurations
  scan        Scan for available MCP servers in various configurations
  as-json     Convert a command or URL to MCP server JSON configuration

Flags:
  -h, --help   help for configs

Global Flags:
  -f, --format string   Output format (table, json, pretty) (default "table")
  -p, --params string   JSON string of parameters to pass to the tool (for call command) (default "{}")

Use "mcp configs [command] --help" for more information about a command.
mcp configs ls
Cursor
  todo server (sse):
    http://52.44.236.251:8000/sse


mcp completion zsh
#compdef mcp
compdef _mcp mcp

# zsh completion for mcp                                  -*- shell-script -*-

__mcp_debug()
{
    local file="$BASH_COMP_DEBUG_FILE"
    if [[ -n ${file} ]]; then
        echo "$*" >> "${file}"
    fi
}

_mcp()
{
    local shellCompDirectiveError=1
    local shellCompDirectiveNoSpace=2
    local shellCompDirectiveNoFileComp=4
    local shellCompDirectiveFilterFileExt=8
    local shellCompDirectiveFilterDirs=16
    local shellCompDirectiveKeepOrder=32

    local lastParam lastChar flagPrefix requestComp out directive comp lastComp noSpace keepOrder
    local -a completions

    __mcp_debug "\n========= starting completion logic =========="
    __mcp_debug "CURRENT: ${CURRENT}, words[*]: ${words[*]}"

    # The user could have moved the cursor backwards on the command-line.
    # We need to trigger completion from the $CURRENT location, so we need
    # to truncate the command-line ($words) up to the $CURRENT location.
    # (We cannot use $CURSOR as its value does not work when a command is an alias.)
    words=("${=words[1,CURRENT]}")
    __mcp_debug "Truncated words[*]: ${words[*]},"

    lastParam=${words[-1]}
    lastChar=${lastParam[-1]}
    __mcp_debug "lastParam: ${lastParam}, lastChar: ${lastChar}"

    # For zsh, when completing a flag with an = (e.g., mcp -n=<TAB>)
    # completions must be prefixed with the flag
    setopt local_options BASH_REMATCH
    if [[ "${lastParam}" =~ '-.*=' ]]; then
        # We are dealing with a flag with an =
        flagPrefix="-P ${BASH_REMATCH}"
    fi

    # Prepare the command to obtain completions
    requestComp="${words[1]} __complete ${words[2,-1]}"
    if [ "${lastChar}" = "" ]; then
        # If the last parameter is complete (there is a space following it)
        # We add an extra empty parameter so we can indicate this to the go completion code.
        __mcp_debug "Adding extra empty parameter"
        requestComp="${requestComp} \"\""
    fi

    __mcp_debug "About to call: eval ${requestComp}"

    # Use eval to handle any environment variables and such
    out=$(eval ${requestComp} 2>/dev/null)
    __mcp_debug "completion output: ${out}"

    # Extract the directive integer following a : from the last line
    local lastLine
    while IFS='\n' read -r line; do
        lastLine=${line}
    done < <(printf "%s\n" "${out[@]}")
    __mcp_debug "last line: ${lastLine}"

    if [ "${lastLine[1]}" = : ]; then
        directive=${lastLine[2,-1]}
        # Remove the directive including the : and the newline
        local suffix
        (( suffix=${#lastLine}+2))
        out=${out[1,-$suffix]}
    else
        # There is no directive specified.  Leave $out as is.
        __mcp_debug "No directive found.  Setting do default"
        directive=0
    fi

    __mcp_debug "directive: ${directive}"
    __mcp_debug "completions: ${out}"
    __mcp_debug "flagPrefix: ${flagPrefix}"

    if [ $((directive & shellCompDirectiveError)) -ne 0 ]; then
        __mcp_debug "Completion received error. Ignoring completions."
        return
    fi

    local activeHelpMarker="_activeHelp_ "
    local endIndex=${#activeHelpMarker}
    local startIndex=$((${#activeHelpMarker}+1))
    local hasActiveHelp=0
    while IFS='\n' read -r comp; do
        # Check if this is an activeHelp statement (i.e., prefixed with $activeHelpMarker)
        if [ "${comp[1,$endIndex]}" = "$activeHelpMarker" ];then
            __mcp_debug "ActiveHelp found: $comp"
            comp="${comp[$startIndex,-1]}"
            if [ -n "$comp" ]; then
                compadd -x "${comp}"
                __mcp_debug "ActiveHelp will need delimiter"
                hasActiveHelp=1
            fi

            continue
        fi

        if [ -n "$comp" ]; then
            # If requested, completions are returned with a description.
            # The description is preceded by a TAB character.
            # For zsh's _describe, we need to use a : instead of a TAB.
            # We first need to escape any : as part of the completion itself.
            comp=${comp//:/\\:}

            local tab="$(printf '\t')"
            comp=${comp//$tab/:}

            __mcp_debug "Adding completion: ${comp}"
            completions+=${comp}
            lastComp=$comp
        fi
    done < <(printf "%s\n" "${out[@]}")

    # Add a delimiter after the activeHelp statements, but only if:
    # - there are completions following the activeHelp statements, or
    # - file completion will be performed (so there will be choices after the activeHelp)
    if [ $hasActiveHelp -eq 1 ]; then
        if [ ${#completions} -ne 0 ] || [ $((directive & shellCompDirectiveNoFileComp)) -eq 0 ]; then
            __mcp_debug "Adding activeHelp delimiter"
            compadd -x "--"
            hasActiveHelp=0
        fi
    fi

    if [ $((directive & shellCompDirectiveNoSpace)) -ne 0 ]; then
        __mcp_debug "Activating nospace."
        noSpace="-S ''"
    fi

    if [ $((directive & shellCompDirectiveKeepOrder)) -ne 0 ]; then
        __mcp_debug "Activating keep order."
        keepOrder="-V"
    fi

    if [ $((directive & shellCompDirectiveFilterFileExt)) -ne 0 ]; then
        # File extension filtering
        local filteringCmd
        filteringCmd='_files'
        for filter in ${completions[@]}; do
            if [ ${filter[1]} != '*' ]; then
                # zsh requires a glob pattern to do file filtering
                filter="\*.$filter"
            fi
            filteringCmd+=" -g $filter"
        done
        filteringCmd+=" ${flagPrefix}"

        __mcp_debug "File filtering command: $filteringCmd"
        _arguments '*:filename:'"$filteringCmd"
    elif [ $((directive & shellCompDirectiveFilterDirs)) -ne 0 ]; then
        # File completion for directories only
        local subdir
        subdir="${completions[1]}"
        if [ -n "$subdir" ]; then
            __mcp_debug "Listing directories in $subdir"
            pushd "${subdir}" >/dev/null 2>&1
        else
            __mcp_debug "Listing directories in ."
        fi

        local result
        _arguments '*:dirname:_files -/'" ${flagPrefix}"
        result=$?
        if [ -n "$subdir" ]; then
            popd >/dev/null 2>&1
        fi
        return $result
    else
        __mcp_debug "Calling _describe"
        if eval _describe $keepOrder "completions" completions $flagPrefix $noSpace; then
            __mcp_debug "_describe found some completions"

            # Return the success of having called _describe
            return 0
        else
            __mcp_debug "_describe did not find completions."
            __mcp_debug "Checking if we should do file completion."
            if [ $((directive & shellCompDirectiveNoFileComp)) -ne 0 ]; then
                __mcp_debug "deactivating file completion"

                # We must return an error code here to let zsh know that there were no
                # completions found by _describe; this is what will trigger other
                # matching algorithms to attempt to find completions.
                # For example zsh can match letters in the middle of words.
                return 1
            else
                # Perform file completion
                __mcp_debug "Activating file completion"

                # We must return the result of this command, so it must be the
                # last command, or else we must store its result to return it.
                _arguments '*:filename:_files'" ${flagPrefix}"
            fi
        fi
    fi
}

# don't run the completion function when being source-ed or eval-ed
if [ "$funcstack[1]" = "_mcp" ]; then
    _mcp
fi
