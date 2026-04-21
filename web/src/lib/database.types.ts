export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  graphql_public: {
    Tables: {
      [_ in never]: never
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      graphql: {
        Args: {
          extensions?: Json
          operationName?: string
          query?: string
          variables?: Json
        }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      archive_queue: {
        Row: {
          attempts: number
          cds_url_hint: string
          claimed_at: string | null
          enqueued_at: string
          enqueued_run_id: string
          id: string
          last_error: string | null
          last_outcome: string | null
          processed_at: string | null
          school_id: string
          school_name: string
          status: string
        }
        Insert: {
          attempts?: number
          cds_url_hint: string
          claimed_at?: string | null
          enqueued_at?: string
          enqueued_run_id: string
          id?: string
          last_error?: string | null
          last_outcome?: string | null
          processed_at?: string | null
          school_id: string
          school_name: string
          status?: string
        }
        Update: {
          attempts?: number
          cds_url_hint?: string
          claimed_at?: string | null
          enqueued_at?: string
          enqueued_run_id?: string
          id?: string
          last_error?: string | null
          last_outcome?: string | null
          processed_at?: string | null
          school_id?: string
          school_name?: string
          status?: string
        }
        Relationships: []
      }
      cds_artifacts: {
        Row: {
          created_at: string
          document_id: string
          id: string
          kind: string
          notes: Json
          producer: string
          producer_version: string
          schema_version: string | null
          sha256: string | null
          storage_path: string
        }
        Insert: {
          created_at?: string
          document_id: string
          id?: string
          kind: string
          notes?: Json
          producer: string
          producer_version: string
          schema_version?: string | null
          sha256?: string | null
          storage_path: string
        }
        Update: {
          created_at?: string
          document_id?: string
          id?: string
          kind?: string
          notes?: Json
          producer?: string
          producer_version?: string
          schema_version?: string | null
          sha256?: string | null
          storage_path?: string
        }
        Relationships: [
          {
            foreignKeyName: "cds_artifacts_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "cds_artifacts_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_manifest"
            referencedColumns: ["document_id"]
          },
          {
            foreignKeyName: "cds_artifacts_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_scorecard"
            referencedColumns: ["document_id"]
          },
        ]
      }
      cds_documents: {
        Row: {
          cds_year: string
          created_at: string
          data_quality_flag: string | null
          detected_year: string | null
          discovered_at: string | null
          extraction_status: string
          id: string
          ipeds_id: string | null
          last_verified_at: string | null
          participation_status: string
          removed_at: string | null
          school_id: string
          school_name: string
          source_format: string | null
          source_page_count: number | null
          source_provenance: string
          source_sha256: string | null
          source_url: string | null
          sub_institutional: string | null
          updated_at: string
        }
        Insert: {
          cds_year: string
          created_at?: string
          data_quality_flag?: string | null
          detected_year?: string | null
          discovered_at?: string | null
          extraction_status?: string
          id?: string
          ipeds_id?: string | null
          last_verified_at?: string | null
          participation_status?: string
          removed_at?: string | null
          school_id: string
          school_name: string
          source_format?: string | null
          source_page_count?: number | null
          source_provenance?: string
          source_sha256?: string | null
          source_url?: string | null
          sub_institutional?: string | null
          updated_at?: string
        }
        Update: {
          cds_year?: string
          created_at?: string
          data_quality_flag?: string | null
          detected_year?: string | null
          discovered_at?: string | null
          extraction_status?: string
          id?: string
          ipeds_id?: string | null
          last_verified_at?: string | null
          participation_status?: string
          removed_at?: string | null
          school_id?: string
          school_name?: string
          source_format?: string | null
          source_page_count?: number | null
          source_provenance?: string
          source_sha256?: string | null
          source_url?: string | null
          sub_institutional?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      cds_llm_cache: {
        Row: {
          cache_read_tokens: number | null
          cache_write_tokens: number | null
          cleaner_version: string
          created_at: string
          document_id: string
          estimated_cost_usd: number | null
          id: string
          input_tokens: number | null
          markdown_sha256: string
          missing_fields_sha256: string
          model_name: string
          output_tokens: number | null
          prompt_version: string
          response_json: Json | null
          schema_version: string
          section_name: string
          source_sha256: string
          status: string
          strategy_version: string
        }
        Insert: {
          cache_read_tokens?: number | null
          cache_write_tokens?: number | null
          cleaner_version?: string
          created_at?: string
          document_id: string
          estimated_cost_usd?: number | null
          id?: string
          input_tokens?: number | null
          markdown_sha256: string
          missing_fields_sha256: string
          model_name: string
          output_tokens?: number | null
          prompt_version: string
          response_json?: Json | null
          schema_version: string
          section_name: string
          source_sha256: string
          status: string
          strategy_version: string
        }
        Update: {
          cache_read_tokens?: number | null
          cache_write_tokens?: number | null
          cleaner_version?: string
          created_at?: string
          document_id?: string
          estimated_cost_usd?: number | null
          id?: string
          input_tokens?: number | null
          markdown_sha256?: string
          missing_fields_sha256?: string
          model_name?: string
          output_tokens?: number | null
          prompt_version?: string
          response_json?: Json | null
          schema_version?: string
          section_name?: string
          source_sha256?: string
          status?: string
          strategy_version?: string
        }
        Relationships: [
          {
            foreignKeyName: "cds_llm_cache_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "cds_llm_cache_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_manifest"
            referencedColumns: ["document_id"]
          },
          {
            foreignKeyName: "cds_llm_cache_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "cds_scorecard"
            referencedColumns: ["document_id"]
          },
        ]
      }
      cleaners: {
        Row: {
          description: string | null
          latest_version: string
          name: string
          output_kind: string
          registered_at: string
          repo_url: string
        }
        Insert: {
          description?: string | null
          latest_version: string
          name: string
          output_kind: string
          registered_at?: string
          repo_url: string
        }
        Update: {
          description?: string | null
          latest_version?: string
          name?: string
          output_kind?: string
          registered_at?: string
          repo_url?: string
        }
        Relationships: []
      }
      school_hosting_observations: {
        Row: {
          auth_required: string | null
          cms: string | null
          file_storage: string | null
          final_url_host: string | null
          id: number
          notes: string | null
          observation_source: string
          observed_at: string
          origin_domain: string | null
          outcome: string | null
          outcome_reason: string | null
          redirect_chain: Json | null
          rendering: string | null
          school_id: string
          seed_url: string | null
          waf: string | null
        }
        Insert: {
          auth_required?: string | null
          cms?: string | null
          file_storage?: string | null
          final_url_host?: string | null
          id?: number
          notes?: string | null
          observation_source: string
          observed_at?: string
          origin_domain?: string | null
          outcome?: string | null
          outcome_reason?: string | null
          redirect_chain?: Json | null
          rendering?: string | null
          school_id: string
          seed_url?: string | null
          waf?: string | null
        }
        Update: {
          auth_required?: string | null
          cms?: string | null
          file_storage?: string | null
          final_url_host?: string | null
          id?: number
          notes?: string | null
          observation_source?: string
          observed_at?: string
          origin_domain?: string | null
          outcome?: string | null
          outcome_reason?: string | null
          redirect_chain?: Json | null
          rendering?: string | null
          school_id?: string
          seed_url?: string | null
          waf?: string | null
        }
        Relationships: []
      }
      scorecard_summary: {
        Row: {
          avg_net_price: number | null
          carnegie_basic: number | null
          cumulative_debt_p90: number | null
          default_rate_3yr: number | null
          earnings_10yr_median: number | null
          earnings_10yr_p25: number | null
          earnings_10yr_p75: number | null
          earnings_6yr_median: number | null
          earnings_8yr_median: number | null
          endowment_end: number | null
          enrollment: number | null
          faculty_salary_avg: number | null
          federal_loan_rate: number | null
          female_share: number | null
          first_generation_share: number | null
          grad_rate_pell: number | null
          graduation_rate_4yr: number | null
          graduation_rate_6yr: number | null
          graduation_rate_8yr: number | null
          hispanic_serving: boolean | null
          historically_black: boolean | null
          instructional_expenditure_fte: number | null
          ipeds_id: string
          locale: number | null
          median_debt_completers: number | null
          median_debt_monthly_payment: number | null
          median_debt_noncompleters: number | null
          median_debt_pell: number | null
          median_family_income: number | null
          net_price_0_30k: number | null
          net_price_110k_plus: number | null
          net_price_30k_48k: number | null
          net_price_48k_75k: number | null
          net_price_75k_110k: number | null
          pell_grant_rate: number | null
          predominantly_black: boolean | null
          refreshed_at: string
          repayment_rate_3yr: number | null
          retention_rate_ft: number | null
          school_name: string
          scorecard_data_year: string
          transfer_out_rate: number | null
        }
        Insert: {
          avg_net_price?: number | null
          carnegie_basic?: number | null
          cumulative_debt_p90?: number | null
          default_rate_3yr?: number | null
          earnings_10yr_median?: number | null
          earnings_10yr_p25?: number | null
          earnings_10yr_p75?: number | null
          earnings_6yr_median?: number | null
          earnings_8yr_median?: number | null
          endowment_end?: number | null
          enrollment?: number | null
          faculty_salary_avg?: number | null
          federal_loan_rate?: number | null
          female_share?: number | null
          first_generation_share?: number | null
          grad_rate_pell?: number | null
          graduation_rate_4yr?: number | null
          graduation_rate_6yr?: number | null
          graduation_rate_8yr?: number | null
          hispanic_serving?: boolean | null
          historically_black?: boolean | null
          instructional_expenditure_fte?: number | null
          ipeds_id: string
          locale?: number | null
          median_debt_completers?: number | null
          median_debt_monthly_payment?: number | null
          median_debt_noncompleters?: number | null
          median_debt_pell?: number | null
          median_family_income?: number | null
          net_price_0_30k?: number | null
          net_price_110k_plus?: number | null
          net_price_30k_48k?: number | null
          net_price_48k_75k?: number | null
          net_price_75k_110k?: number | null
          pell_grant_rate?: number | null
          predominantly_black?: boolean | null
          refreshed_at?: string
          repayment_rate_3yr?: number | null
          retention_rate_ft?: number | null
          school_name: string
          scorecard_data_year: string
          transfer_out_rate?: number | null
        }
        Update: {
          avg_net_price?: number | null
          carnegie_basic?: number | null
          cumulative_debt_p90?: number | null
          default_rate_3yr?: number | null
          earnings_10yr_median?: number | null
          earnings_10yr_p25?: number | null
          earnings_10yr_p75?: number | null
          earnings_6yr_median?: number | null
          earnings_8yr_median?: number | null
          endowment_end?: number | null
          enrollment?: number | null
          faculty_salary_avg?: number | null
          federal_loan_rate?: number | null
          female_share?: number | null
          first_generation_share?: number | null
          grad_rate_pell?: number | null
          graduation_rate_4yr?: number | null
          graduation_rate_6yr?: number | null
          graduation_rate_8yr?: number | null
          hispanic_serving?: boolean | null
          historically_black?: boolean | null
          instructional_expenditure_fte?: number | null
          ipeds_id?: string
          locale?: number | null
          median_debt_completers?: number | null
          median_debt_monthly_payment?: number | null
          median_debt_noncompleters?: number | null
          median_debt_pell?: number | null
          median_family_income?: number | null
          net_price_0_30k?: number | null
          net_price_110k_plus?: number | null
          net_price_30k_48k?: number | null
          net_price_48k_75k?: number | null
          net_price_75k_110k?: number | null
          pell_grant_rate?: number | null
          predominantly_black?: boolean | null
          refreshed_at?: string
          repayment_rate_3yr?: number | null
          retention_rate_ft?: number | null
          school_name?: string
          scorecard_data_year?: string
          transfer_out_rate?: number | null
        }
        Relationships: []
      }
    }
    Views: {
      cds_manifest: {
        Row: {
          canonical_year: string | null
          cds_year: string | null
          data_quality_flag: string | null
          detected_year: string | null
          discovered_at: string | null
          document_id: string | null
          extraction_status: string | null
          ipeds_id: string | null
          last_verified_at: string | null
          latest_canonical_artifact_id: string | null
          participation_status: string | null
          removed_at: string | null
          school_id: string | null
          school_name: string | null
          source_format: string | null
          source_storage_path: string | null
          source_url: string | null
          sub_institutional: string | null
        }
        Insert: {
          canonical_year?: never
          cds_year?: string | null
          data_quality_flag?: string | null
          detected_year?: string | null
          discovered_at?: string | null
          document_id?: string | null
          extraction_status?: string | null
          ipeds_id?: string | null
          last_verified_at?: string | null
          latest_canonical_artifact_id?: never
          participation_status?: string | null
          removed_at?: string | null
          school_id?: string | null
          school_name?: string | null
          source_format?: string | null
          source_storage_path?: never
          source_url?: string | null
          sub_institutional?: string | null
        }
        Update: {
          canonical_year?: never
          cds_year?: string | null
          data_quality_flag?: string | null
          detected_year?: string | null
          discovered_at?: string | null
          document_id?: string | null
          extraction_status?: string | null
          ipeds_id?: string | null
          last_verified_at?: string | null
          latest_canonical_artifact_id?: never
          participation_status?: string | null
          removed_at?: string | null
          school_id?: string | null
          school_name?: string | null
          source_format?: string | null
          source_storage_path?: never
          source_url?: string | null
          sub_institutional?: string | null
        }
        Relationships: []
      }
      cds_scorecard: {
        Row: {
          avg_net_price: number | null
          cds_year: string | null
          data_quality_flag: string | null
          default_rate_3yr: number | null
          document_id: string | null
          earnings_10yr_median: number | null
          earnings_10yr_p25: number | null
          earnings_10yr_p75: number | null
          endowment_end: number | null
          extraction_status: string | null
          federal_loan_rate: number | null
          first_generation_share: number | null
          grad_rate_pell: number | null
          graduation_rate_6yr: number | null
          instructional_expenditure_fte: number | null
          ipeds_id: string | null
          latest_canonical_artifact_id: string | null
          median_debt_completers: number | null
          median_debt_monthly_payment: number | null
          median_family_income: number | null
          net_price_0_30k: number | null
          net_price_110k_plus: number | null
          net_price_30k_48k: number | null
          net_price_48k_75k: number | null
          net_price_75k_110k: number | null
          pell_grant_rate: number | null
          repayment_rate_3yr: number | null
          retention_rate_ft: number | null
          school_id: string | null
          school_name: string | null
          scorecard_data_year: string | null
          source_format: string | null
          source_storage_path: string | null
        }
        Relationships: []
      }
      latest_school_hosting: {
        Row: {
          auth_required: string | null
          cms: string | null
          file_storage: string | null
          final_url_host: string | null
          notes: string | null
          observation_source: string | null
          observed_at: string | null
          origin_domain: string | null
          outcome: string | null
          outcome_reason: string | null
          redirect_chain: Json | null
          rendering: string | null
          school_id: string | null
          seed_url: string | null
          waf: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      claim_archive_queue_row: {
        Args: never
        Returns: {
          attempts: number
          cds_url_hint: string
          claimed_at: string | null
          enqueued_at: string
          enqueued_run_id: string
          id: string
          last_error: string | null
          last_outcome: string | null
          processed_at: string | null
          school_id: string
          school_name: string
          status: string
        }
        SetofOptions: {
          from: "*"
          to: "archive_queue"
          isOneToOne: true
          isSetofReturn: false
        }
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const
