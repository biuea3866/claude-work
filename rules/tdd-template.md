# TDD 템플릿 가이드

## 필수 섹션

TDD(Technical Design Document)는 아래 섹션을 모두 포함합니다.

```markdown
# {기능명} TDD

## Background
{프로젝트 배경과 동기}

## Overview
{전체 요약 — 무엇을, 왜, 어떻게}

## Terminology
{용어 정의 테이블}

## Define Problem
### AS-IS
{현재 구조와 문제점}
### TO-BE
{목표 구조}

## Possible Solutions
### 벤치마킹 참조 제품
| 제품명 | 카테고리 | 참조 URL | 참조 패턴 |
### 방안 비교
| 방안 | 설명 | 왜 채택 | 미채택 대안 |

## Detail Design
### 클래스 역할 정의
#### 도메인 모델
| 클래스명 | 역할 | 핵심 책임 |
#### 서비스 클래스
| 클래스명 | 역할 | 입력 → 출력 | 의존 |
### AS-IS / TO-BE 비교
### Component Diagram (Mermaid flowchart LR)
### Sequence Diagram (Mermaid)

## ERD
{Mermaid erDiagram — DDL 전문은 티켓에, TDD에는 요약만}

## Testing Plan
{테스트 전략, 레벨별 범위}

## Release Scenario
{배포 순서, 마이그레이션 선/후 조건, 롤백 플랜}

## Project Information
{일정, 담당자, Jira Epic}

## Document History
| 날짜 | 변경 내용 | 작성자 |
```

## 작성 규칙

### 방안 비교 테이블

- "무엇인가" 대신 "설명" 열을 사용합니다.
- 각 방안을 풀어서 기술합니다. 표만 나열하지 않습니다.
- 채택 이유와 미채택 대안을 명시합니다.

### 상태값 한글화

- 완료, 실패, 부분 실패, 진행 중, 대기
- enum 이름은 영문 유지, 설명은 한글로 씁니다.

### 기술 용어 한글화

| 원문 | 한글 |
|------|------|
| fire-and-forget | 결과 미추적 |
| 4-phase | 4단계 그룹 병렬 |
| blue-green | 블루그린 배포 |
| shadow traffic | 섀도 트래픽 |
| dual write | 이중 기록 |
| strangler fig | 점진적 대체 |

### 선택 섹션

- **FE 영향 분석**: API 변경/이관 시 필수 (FE 의존 서비스, 전환 전략, 핵심 리스크)
- **Security Information**: 보안 관련 변경 시
- **Milestone**: 단계별 마일스톤이 있을 때
