export interface User {
  id: number
  username: string
  email: string | null
  is_active: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface TransactionItem {
  id: number
  platform: string
  occurred_at: string
  type: string
  amount: string
  merchant: string | null
  item: string | null
  note: string | null
  auto_provider: string | null
  auto_reason: string | null
  auto_confidence: string | null
  auto_category_id: number | null
  final_category_id: number | null
  needs_review: boolean
}

export interface CategoryItem {
  id: number
  user_id: number | null
  parent_id: number | null
  name: string
  description: string | null
  is_system: boolean
  is_active: boolean
}
