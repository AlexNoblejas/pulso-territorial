# Programa la estación local en el Programador de tareas de Windows (lunes y jueves, 6:30 a. m.,
# y al iniciar sesión si la laptop estuvo apagada). Ejecutar una sola vez. Para quitarla:
#   Unregister-ScheduledTask -TaskName 'PulsoTerritorial-EstacionLocal' -Confirm:$false
$script = Join-Path $PSScriptRoot 'estacion_local.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $PSScriptRoot
$triggers = @(
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Thursday -At 6:30am),
    (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME)
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'PulsoTerritorial-EstacionLocal' -Action $action -Trigger $triggers -Settings $settings -Description 'Actualiza SINIA y GEOPERÚ (bloquean a GitHub) y sube el resultado al repositorio.' -Force
