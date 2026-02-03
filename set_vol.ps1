param([int]$target_vol)

$obj = New-Object -ComObject WScript.Shell

# 1. Reset to 0 (Mute approach is unreliable for setting levels, so we just squash it down)
# Press Volume Down 60 times to guarantee 0
for ($i = 0; $i -lt 60; $i++) { 
    $obj.SendKeys([char]174)
    Start-Sleep -Milliseconds 5
}

# 2. Calculate steps up
# Each key press is usually 2%
if ($target_vol -gt 0) {
    $steps = [math]::Round($target_vol / 2)
    
    for ($i = 0; $i -lt $steps; $i++) { 
        $obj.SendKeys([char]175)
        Start-Sleep -Milliseconds 5
    }
}
