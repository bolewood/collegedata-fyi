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
        ]
      }
      cds_documents: {
        Row: {
          cds_year: string
          created_at: string
          detected_year: string | null
          discovered_at: string | null
          extraction_status: string
          id: string
          last_verified_at: string | null
          participation_status: string
          removed_at: string | null
          school_id: string
          school_name: string
          source_format: string | null
          source_page_count: number | null
          source_sha256: string | null
          source_url: string | null
          sub_institutional: string | null
          updated_at: string
        }
        Insert: {
          cds_year: string
          created_at?: string
          detected_year?: string | null
          discovered_at?: string | null
          extraction_status?: string
          id?: string
          last_verified_at?: string | null
          participation_status?: string
          removed_at?: string | null
          school_id: string
          school_name: string
          source_format?: string | null
          source_page_count?: number | null
          source_sha256?: string | null
          source_url?: string | null
          sub_institutional?: string | null
          updated_at?: string
        }
        Update: {
          cds_year?: string
          created_at?: string
          detected_year?: string | null
          discovered_at?: string | null
          extraction_status?: string
          id?: string
          last_verified_at?: string | null
          participation_status?: string
          removed_at?: string | null
          school_id?: string
          school_name?: string
          source_format?: string | null
          source_page_count?: number | null
          source_sha256?: string | null
          source_url?: string | null
          sub_institutional?: string | null
          updated_at?: string
        }
        Relationships: []
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
    }
    Views: {
      cds_manifest: {
        Row: {
          canonical_year: string | null
          cds_year: string | null
          detected_year: string | null
          discovered_at: string | null
          document_id: string | null
          extraction_status: string | null
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
          detected_year?: string | null
          discovered_at?: string | null
          document_id?: string | null
          extraction_status?: string | null
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
          detected_year?: string | null
          discovered_at?: string | null
          document_id?: string | null
          extraction_status?: string | null
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
  public: {
    Enums: {},
  },
} as const
