#!/usr/bin/env bash
# 시안에 쓰는 폰트를 Google Fonts 에서 내려받는다.
# 세 폰트 모두 SIL Open Font License 1.1 이라 재배포와 상업적 사용이 가능하다.
# fonts/ 에 이미 커밋돼 있으므로 평소에는 실행할 필요가 없다.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p fonts

fetch() {  # fetch <google-fonts-query> <출력파일명>
  local url
  url=$(curl -fsS -A "Mozilla/5.0" \
        "https://fonts.googleapis.com/css2?family=$1&subset=korean" \
        | grep -oE 'https://[^)]+\.ttf' | head -1)
  [ -n "$url" ] || { echo "URL 못 찾음: $1" >&2; return 1; }
  curl -fsSL -A "Mozilla/5.0" -o "fonts/$2" "$url"
  echo "fonts/$2  <-  $1"
}

fetch "Hahmlet:wght@700"        Hahmlet-700.ttf
fetch "Nanum+Myeongjo:wght@800" NanumMyeongjo-800.ttf
fetch "Song+Myung"              SongMyung.ttf

# 다른 톤이 궁금하면 아래도 받아서 generate.py 의 FACES 에 넣어보면 된다.
#   "Hahmlet:wght@900"      더 무겁고 대비가 낮은 슬랩에 가까운 톤
#   "Gowun+Batang:wght@700" 획이 둥글고 부드러운 바탕
#   "Noto+Serif+KR:wght@900" 무난한 현대 명조
#   "Gasoek+One"            초헤비 디스플레이 (세리프 없음)
