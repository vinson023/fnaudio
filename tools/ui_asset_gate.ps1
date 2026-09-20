$ErrorActionPreference = "Stop"

function Get-DeclaredUiScriptPaths {
    <#
        Discovery of the UI modules that the offline gate has to syntax check.

        The pattern must tolerate any attribute order and any extra attribute
        (defer, type, crossorigin). A rule that only matches `<script src="`
        quietly stops finding modules as soon as the markup grows an attribute,
        and the gate would keep reporting success with no UI coverage at all.
    #>
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$IndexText
    )

    # The captured path stops before any query: the packaged index.html carries
    # the real build stamp instead of the __FNAUDIO_ASSET_BUILD__ placeholder.
    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($IndexText, '(?i)<script\b[^>]*\bsrc="([^"?#]+\.(?:js|mjs))(?:\?[^"]*)?"')) {
        $relative = $match.Groups[1].Value.Trim().Replace("\", "/")
        if ($relative.Split("/") -contains "..") {
            throw "index.html declares a UI script outside the UI root: $relative"
        }
        if ($relative -match '^(?:[A-Za-z][A-Za-z0-9+.-]*:)?//') {
            # A remote script has no local file for node --check to read.
            continue
        }
        if ($relative -eq "app.js") {
            # The gate checks the entry module explicitly.
            continue
        }
        $paths.Add($relative)
    }
    return @($paths | Sort-Object -Unique)
}
