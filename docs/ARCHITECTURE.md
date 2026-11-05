# 하네스 구조

2026-11-05 (Asia/Seoul) · 확정한 하네스 구조를 기준으로 아키텍처 설계를 다시 진행한다.

## 확정 하네스 구조

![외부 하네스의 워크플로 제어·다중 에이전트·도구 통합·상태 및 기억·검증·모니터링이 Codex SDK / App Server / CLI를 통해 Codex Core와 연결되는 구조](diagrams/codex_external_harness_architecture.png)

[첨부 HTML 원본](diagrams/codex_external_harness_architecture.html)

## 사용 구조

```mermaid
flowchart LR
    I["인터페이스"] <--> H["하네스"] <--> M["모델"]

    style I fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style H fill:#effaf5,stroke:#8fd1b8,color:#1e293b
    style M fill:#f3f4f6,stroke:#94a3b8,color:#1e293b
```

여기서 하네스는 위의 외부 하네스, Codex 연결 계층과 Codex Core를 포함한다.
