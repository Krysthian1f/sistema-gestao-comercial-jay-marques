param(
    [switch]$PreflightOnly,
    [switch]$InitializeApproved
)

$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$scriptPath = if ($PreflightOnly -or $InitializeApproved) {
    Join-Path $PSScriptRoot 'init_neon_db.py'
} else {
    Join-Path $PSScriptRoot 'testar_neon.py'
}

if ($PreflightOnly -and $InitializeApproved) {
    Write-Output 'ERRO: escolha somente um modo: -PreflightOnly ou -InitializeApproved.'
    return
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Output 'ERRO: ambiente virtual do projeto não encontrado.'
    return
}
if (-not (Test-Path -LiteralPath $scriptPath)) {
    Write-Output 'ERRO: o script Python solicitado não foi encontrado na pasta do projeto.'
    return
}

$neonHost = (Read-Host 'Host pooler do Neon (somente hostname)').Trim()
if ($neonHost -notmatch '^[A-Za-z0-9-]+-pooler(\.[A-Za-z0-9-]+)+\.neon\.tech$') {
    Write-Output 'ERRO: hostname fora do formato esperado para o pooler Neon.'
    return
}

$securePassword = Read-Host 'Senha da role neondb_owner' -AsSecureString
$passwordPointer = [IntPtr]::Zero
try {
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $encodedPassword = [Uri]::EscapeDataString($plainPassword)
    $env:DATABASE_URL = "postgresql+psycopg://neondb_owner:${encodedPassword}@${neonHost}/neondb?sslmode=require&channel_binding=require"
}
catch {
    Write-Output 'ERRO: não foi possível preparar a conexão. Nenhum detalhe ou credencial foi exibido.'
    return
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    if ($securePassword) {
        $securePassword.Dispose()
    }
    Remove-Variable plainPassword, encodedPassword, securePassword, passwordPointer -ErrorAction SilentlyContinue
}

if ($InitializeApproved) {
    # The user explicitly authorized creation of only missing tables.
    $approvalPhrase = 'CRIAR TABELAS NO NEON'
    $testOutput = $approvalPhrase | & $pythonPath $scriptPath 2>&1
    $testExitCode = $LASTEXITCODE
    $testOutput | ForEach-Object { Write-Output "$($_)" }
    if ($testExitCode -ne 0) {
        Write-Output 'Inicialização não concluída; confira a mensagem acima. Nenhuma migração ou exclusão foi solicitada.'
    }
    return
}

if ($PreflightOnly) {
    $testOutput = & $pythonPath $scriptPath --preflight-only 2>&1
} else {
    $testOutput = & $pythonPath $scriptPath 2>&1
}
$testExitCode = $LASTEXITCODE
if ($PreflightOnly) {
    $testOutput | ForEach-Object { Write-Output "$($_)" }
    if ($testExitCode -ne 0) {
        Write-Output 'Pré-verificação não concluída; nenhuma alteração foi solicitada pelo modo somente leitura.'
    }
    return
}
if ($testExitCode -eq 0) {
    Write-Output 'RESULTADO: conexão PostgreSQL validada; TLS e SELECT 1 confirmados.'
    return
}

$safeDiagnostic = $testOutput |
    ForEach-Object {
        $line = "$($_)"
        if ($line -match '(Falha na conexão ou consulta:.*)$') {
            $Matches[1]
        }
    } |
    Select-Object -First 1

if ($safeDiagnostic) {
    Write-Output $safeDiagnostic
}
else {
    Write-Output 'RESULTADO: teste não validado; nenhuma URL, credencial ou mensagem bruta foi exibida.'
}
