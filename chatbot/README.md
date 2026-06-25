# Custom n8n Chatbot UI

n8n **Chat Trigger** webhook 에 연결되는 커스텀 챗봇 화면입니다.
빌드/의존성 없이 정적 파일(HTML/CSS/JS)로만 동작합니다.

## 로컬 실행

> `file://` 로 직접 열면 브라우저 CORS 정책에 막히므로, **꼭 정적 서버로** 띄우세요.

```bash
cd chatbot
python3 -m http.server 8000
# 또는: npx serve .
```

브라우저에서 <http://localhost:8000> 접속.

## n8n 쪽 설정 (중요)

1. 워크플로우의 **Chat Trigger** 노드를 엽니다.
2. **Options → Allowed Origins (CORS)** 에 로컬 주소를 추가합니다.
   - 빠른 테스트: `*`
   - 권장: `http://localhost:8000`
3. 워크플로우를 **Active** 로 켭니다. (production `/webhook/...` URL 사용)

CORS 를 안 열면 브라우저 콘솔에 CORS 에러가 뜨고 메시지가 전송되지 않습니다.

## webhook 주소 변경

`app.js` 상단의 `CONFIG.webhookUrl` 값을 바꾸면 됩니다.
임시로는 `http://localhost:8000/?webhook=<URL>` 처럼 쿼리 파라미터로도 교체 가능합니다.

## 커스터마이즈

- **색/디자인**: `styles.css` 상단의 CSS 변수 (`--accent`, `--user-bubble`, `--bot-bubble` 등)
- **인사말 / 봇 이름**: `app.js` 의 `CONFIG.welcomeMessage`, `CONFIG.botName`
- **다크/라이트 모드**: 헤더 우측 버튼으로 전환 (시스템 설정 자동 감지)

## 동작 방식

- 사용자가 입력하면 webhook 으로 `{ action: "sendMessage", sessionId, chatInput }` 를 POST
- 응답에서 `output` / `text` / `response` 등 다양한 키를 자동으로 찾아 표시
- `sessionId` 는 브라우저에 저장되어 대화 맥락(메모리)이 유지됩니다
- 봇 답변은 마크다운으로 렌더링되며 DOMPurify 로 XSS 방지 처리됩니다
