$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath 'demo/phase-e-raw.webm')) {
    throw 'Run from the repository root with demo/phase-e-raw.webm present.'
}

$ffmpegArgs = @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-ss', '0', '-t', '15', '-i', 'demo/phase-e-raw.webm',
    '-ss', '150', '-t', '21', '-i', 'demo/phase-e-raw.webm',
    '-ss', '219', '-t', '9', '-i', 'demo/phase-e-raw.webm',
    '-ss', '290', '-t', '30', '-i', 'demo/phase-e-raw.webm',
    '-ss', '360', '-t', '28', '-i', 'demo/phase-e-raw.webm',
    '-ss', '400', '-t', '26', '-i', 'demo/phase-e-raw.webm',
    '-ss', '565', '-t', '21', '-i', 'demo/phase-e-raw.webm',
    '-ss', '775', '-t', '15', '-i', 'demo/phase-e-raw.webm',
    '-loop', '1', '-framerate', '25', '-t', '15', '-i', 'demo/phase-e-card.png',
    '-filter_complex', '[0:v]fps=25,setpts=PTS-STARTPTS[v0];[1:v]fps=25,setpts=PTS-STARTPTS[v1];[2:v]fps=25,setpts=PTS-STARTPTS[v2];[3:v]fps=25,setpts=PTS-STARTPTS[v3];[4:v]fps=25,setpts=PTS-STARTPTS[v4];[5:v]fps=25,setpts=PTS-STARTPTS[v5];[6:v]fps=25,setpts=PTS-STARTPTS[v6];[7:v]fps=25,setpts=PTS-STARTPTS[v7];[8:v]scale=1600:900,fps=25,setpts=PTS-STARTPTS[v8];[v0][v1][v2][v3][v4][v5][v6][v7][v8]concat=n=9:v=1:a=0,ass=demo/phase-e-captions.ass,format=yuv420p[out]',
    '-map', '[out]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
    '-movflags', '+faststart', 'demo/phase-e-demo.mp4'
)

& ffmpeg @ffmpegArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
