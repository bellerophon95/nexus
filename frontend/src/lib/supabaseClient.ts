import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://jqnwgzcmrjnmulkpgtup.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxbndnemNtcmpubXVsa3BndHVwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ2NjE3MzcsImV4cCI6MjA5MDIzNzczN30.4v_p7z38o_S6Ow717HvolE_SaQ6OCMgXrkZuqpN_UWY';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
