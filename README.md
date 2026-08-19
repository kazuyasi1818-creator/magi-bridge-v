# MAGI Bridge v4

GPT → Claude監査 → GPT改訂 → Claude最終判定を4回の短いAPI通信で実行します。

v4の変更点:
- 最終Claude判定を短くしてiPhone/Safariでの通信失敗を減らす
- 段階ごとに出力上限を分け、コストと待ち時間を抑える
- 実使用トークンからAPI料金を概算表示

必要なVercel環境変数:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- OPENAI_MODEL（任意、現在の動作確認済み設定は gpt-4.1）
- ANTHROPIC_MODEL（任意、既定 claude-sonnet-4-6）

任意の出力上限:
- MAGI_GPT_INITIAL_TOKENS
- MAGI_CLAUDE_AUDIT_TOKENS
- MAGI_GPT_REVISE_TOKENS
- MAGI_CLAUDE_VERDICT_TOKENS
