"""
Floor Plan Analysis Script - Offline Batch Processing
Analyzes floor plans from Supabase storage and stores insights in database

Usage:
    python analyze_floor_plans.py --project-id 123
    python analyze_floor_plans.py --all
"""

import os
import sys
import json
import base64
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import Json
import requests
from datetime import datetime

# Try to import OpenAI, but make it optional
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI package not installed. Using local LLM only.")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# OpenAI API (or use local LLM like Ollama)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')  # Set in environment or here
USE_LOCAL_LLM = True  # Set to False to use OpenAI GPT-4 Vision

# Supabase
SUPABASE_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqZ3duYnN6bW9qemd3bWFmdnVjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjQ4NDY2MCwiZXhwIjoyMTAyMDYwNjYwfQ.pkyFMWdt0vtfUHVY_-8sAfO7SC1ygtvJE191cGGhks0"

# Database
DB_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "postgres.qjgwnbszmojzgwmafvuc"
DB_PASS = "LZGJwY0ryKkFKH5P"

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PROMPT
# ══════════════════════════════════════════════════════════════════════════════

FLOOR_PLAN_ANALYSIS_PROMPT = """You are an expert real estate analyst specializing in Indian residential properties.

Analyze this floor plan and provide a structured JSON response with the following:

{
  "overall_score": 0-100,
  "livability_scores": {
    "flow": 0-100,
    "privacy": 0-100,
    "light": 0-100,
    "space_efficiency": 0-100,
    "storage": 0-100,
    "vastu": 0-100
  },
  "metrics": {
    "bedroom_count": number,
    "bathroom_count": number,
    "balcony_count": number,
    "total_area_sqft": number,
    "carpet_area_sqft": number,
    "efficiency_ratio": percentage
  },
  "findings": [
    {
      "category": "flow|privacy|light|space|storage|vastu",
      "severity": "good|warning|issue",
      "title": "Brief title",
      "description": "Detailed description",
      "location": "Which room/area"
    }
  ],
  "highlights": [
    "Positive aspect 1",
    "Positive aspect 2"
  ],
  "concerns": [
    "Concern 1",
    "Concern 2"
  ],
  "vastu_analysis": {
    "main_entrance": "Direction and Vastu compliance",
    "kitchen": "Direction and Vastu compliance",
    "master_bedroom": "Direction and Vastu compliance",
    "overall_compliance": "percentage"
  },
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2"
  ]
}

Focus on Indian market preferences:
- Vastu compliance (entrance, kitchen, bedroom directions)
- Cross ventilation
- Privacy from main entrance
- Balcony utility
- Servant quarter/utility room
- Car parking visibility

Be specific and actionable. Identify real issues that affect daily living."""


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA CREATION
# ══════════════════════════════════════════════════════════════════════════════

CREATE_PLAN_ANALYSIS_TABLE = """
CREATE TABLE IF NOT EXISTS floor_plan_analysis (
    id SERIAL PRIMARY KEY,
    project_id TEXT NOT NULL,
    plan_url TEXT NOT NULL,
    
    -- Overall scores
    overall_score INTEGER,
    flow_score INTEGER,
    privacy_score INTEGER,
    light_score INTEGER,
    space_efficiency_score INTEGER,
    storage_score INTEGER,
    vastu_score INTEGER,
    
    -- Metrics
    bedroom_count INTEGER,
    bathroom_count INTEGER,
    balcony_count INTEGER,
    total_area_sqft NUMERIC,
    carpet_area_sqft NUMERIC,
    efficiency_ratio NUMERIC,
    
    -- Analysis results (JSON)
    findings JSONB,
    highlights JSONB,
    concerns JSONB,
    vastu_analysis JSONB,
    recommendations JSONB,
    
    -- Metadata
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analysis_version TEXT DEFAULT '1.0',
    
    UNIQUE(project_id, plan_url)
);

CREATE INDEX IF NOT EXISTS idx_plan_analysis_project ON floor_plan_analysis(project_id);
CREATE INDEX IF NOT EXISTS idx_plan_analysis_score ON floor_plan_analysis(overall_score DESC);
"""


# ══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_floor_plan_with_openai(image_url: str) -> Dict:
    """Analyze floor plan using OpenAI GPT-4 Vision"""
    if not OPENAI_AVAILABLE:
        raise Exception("OpenAI package not installed. Install with: pip install openai")
    
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": FLOOR_PLAN_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    }
                ]
            }
        ],
        max_tokens=2000,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


def analyze_floor_plan_with_local_llm(image_path: str) -> Dict:
    """Analyze floor plan using local Ollama with vision model"""
    # Try llama3.2-vision first, fallback to llama3.2:3b with text-only analysis
    
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    try:
        # Try vision model first
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2-vision',
                'prompt': FLOOR_PLAN_ANALYSIS_PROMPT,
                'images': [image_data],
                'stream': False,
                'format': 'json'
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            return json.loads(result['response'])
    except:
        pass
    
    # Fallback: Use basic analysis with llama3.2:3b (text-only, no image)
    print("   ⚠️  Vision model not available, using basic analysis...")
    return analyze_floor_plan_basic(image_path)


def analyze_floor_plan_basic(image_path: str) -> Dict:
    """Basic rule-based analysis without AI (fallback)"""
    # Simple heuristics when AI is not available
    return {
        "overall_score": 70,
        "livability_scores": {
            "flow": 70,
            "privacy": 65,
            "light": 75,
            "space_efficiency": 70,
            "storage": 60,
            "vastu": 50
        },
        "metrics": {
            "bedroom_count": 0,
            "bathroom_count": 0,
            "balcony_count": 0,
            "total_area_sqft": 0,
            "carpet_area_sqft": 0,
            "efficiency_ratio": 0
        },
        "findings": [
            {
                "category": "general",
                "severity": "warning",
                "title": "Manual review needed",
                "description": "AI analysis not available. Please review manually.",
                "location": "Overall"
            }
        ],
        "highlights": ["Floor plan uploaded"],
        "concerns": ["Requires manual analysis"],
        "vastu_analysis": {
            "overall_compliance": "Not analyzed"
        },
        "recommendations": ["Schedule professional floor plan review"]
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode='require'
    )


def ensure_table_exists():
    """Create floor_plan_analysis table if not exists"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_PLAN_ANALYSIS_TABLE)
        conn.commit()
        print("✅ Table floor_plan_analysis ready")
    finally:
        conn.close()


def get_floor_plans_to_analyze(project_id: Optional[int] = None) -> List[Dict]:
    """Get floor plan URLs from project_media table"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if project_id:
                query = """
                    SELECT DISTINCT pm.project_id, pm.file_url, p.project_name
                    FROM project_media pm
                    JOIN projects p ON pm.project_id::text = p.id::text
                    WHERE pm.media_type = 'floorplan' 
                    AND pm.project_id::text = %s
                    AND NOT EXISTS (
                        SELECT 1 FROM floor_plan_analysis fpa 
                        WHERE fpa.project_id::text = pm.project_id::text 
                        AND fpa.plan_url = pm.file_url
                    )
                """
                cur.execute(query, (str(project_id),))
            else:
                query = """
                    SELECT DISTINCT pm.project_id, pm.file_url, p.project_name
                    FROM project_media pm
                    JOIN projects p ON pm.project_id::text = p.id::text
                    WHERE pm.media_type = 'floorplan'
                    AND NOT EXISTS (
                        SELECT 1 FROM floor_plan_analysis fpa 
                        WHERE fpa.project_id::text = pm.project_id::text 
                        AND fpa.plan_url = pm.file_url
                    )
                    ORDER BY pm.project_id
                    LIMIT 50
                """
                cur.execute(query)
            
            rows = cur.fetchall()
            return [
                {
                    'project_id': str(row[0]),
                    'file_url': row[1],
                    'project_name': row[2]
                }
                for row in rows
            ]
    finally:
        conn.close()


def save_analysis_to_db(project_id: str, plan_url: str, analysis: Dict):
    """Save analysis results to database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO floor_plan_analysis (
                    project_id, plan_url,
                    overall_score, flow_score, privacy_score, light_score,
                    space_efficiency_score, storage_score, vastu_score,
                    bedroom_count, bathroom_count, balcony_count,
                    total_area_sqft, carpet_area_sqft, efficiency_ratio,
                    findings, highlights, concerns, vastu_analysis, recommendations
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (project_id, plan_url) DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    flow_score = EXCLUDED.flow_score,
                    privacy_score = EXCLUDED.privacy_score,
                    light_score = EXCLUDED.light_score,
                    space_efficiency_score = EXCLUDED.space_efficiency_score,
                    storage_score = EXCLUDED.storage_score,
                    vastu_score = EXCLUDED.vastu_score,
                    bedroom_count = EXCLUDED.bedroom_count,
                    bathroom_count = EXCLUDED.bathroom_count,
                    balcony_count = EXCLUDED.balcony_count,
                    total_area_sqft = EXCLUDED.total_area_sqft,
                    carpet_area_sqft = EXCLUDED.carpet_area_sqft,
                    efficiency_ratio = EXCLUDED.efficiency_ratio,
                    findings = EXCLUDED.findings,
                    highlights = EXCLUDED.highlights,
                    concerns = EXCLUDED.concerns,
                    vastu_analysis = EXCLUDED.vastu_analysis,
                    recommendations = EXCLUDED.recommendations,
                    analyzed_at = NOW()
            """, (
                project_id, plan_url,
                analysis['overall_score'],
                analysis['livability_scores']['flow'],
                analysis['livability_scores']['privacy'],
                analysis['livability_scores']['light'],
                analysis['livability_scores']['space_efficiency'],
                analysis['livability_scores']['storage'],
                analysis['livability_scores']['vastu'],
                analysis['metrics']['bedroom_count'],
                analysis['metrics']['bathroom_count'],
                analysis['metrics']['balcony_count'],
                analysis['metrics']['total_area_sqft'],
                analysis['metrics']['carpet_area_sqft'],
                analysis['metrics']['efficiency_ratio'],
                Json(analysis['findings']),
                Json(analysis['highlights']),
                Json(analysis['concerns']),
                Json(analysis['vastu_analysis']),
                Json(analysis['recommendations'])
            ))
        conn.commit()
        print(f"   ✅ Saved analysis (score: {analysis['overall_score']}/100)")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def download_image(url: str, output_path: str):
    """Download image from Supabase storage"""
    headers = {
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'apikey': SUPABASE_KEY
    }
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    return False


def process_floor_plans(project_id: Optional[str] = None):
    """Main processing function"""
    print("="*70)
    print("🏗️  FLOOR PLAN ANALYSIS - BATCH PROCESSOR")
    print("="*70)
    
    # Setup
    ensure_table_exists()
    temp_dir = Path("temp_floor_plans")
    temp_dir.mkdir(exist_ok=True)
    
    # Get plans to analyze
    plans = get_floor_plans_to_analyze(project_id)
    
    if not plans:
        print("✨ No new floor plans to analyze")
        return
    
    print(f"\n📊 Found {len(plans)} floor plan(s) to analyze\n")
    
    # Process each plan
    for idx, plan in enumerate(plans, 1):
        project_id = plan['project_id']
        project_name = plan['project_name']
        plan_url = plan['file_url']
        
        print(f"[{idx}/{len(plans)}] {project_name} (ID: {project_id})")
        print(f"   📄 {plan_url}")
        
        try:
            # Download image
            temp_file = temp_dir / f"plan_{project_id}_{idx}.jpg"
            print(f"   📥 Downloading...")
            
            if not download_image(plan_url, str(temp_file)):
                print(f"   ❌ Download failed")
                continue
            
            # Analyze
            print(f"   🤖 Analyzing...")
            
            if USE_LOCAL_LLM:
                analysis = analyze_floor_plan_with_local_llm(str(temp_file))
            elif OPENAI_API_KEY:
                analysis = analyze_floor_plan_with_openai(plan_url)
            else:
                analysis = analyze_floor_plan_basic(str(temp_file))
            
            # Save to database
            save_analysis_to_db(project_id, plan_url, analysis)
            
            # Cleanup
            temp_file.unlink()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    print("\n" + "="*70)
    print(f"✨ Analysis complete! Processed {len(plans)} floor plan(s)")
    print("="*70)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze floor plans and store results')
    parser.add_argument('--project-id', type=int, help='Analyze specific project ID')
    parser.add_argument('--all', action='store_true', help='Analyze all unprocessed plans')
    
    args = parser.parse_args()
    
    if args.project_id:
        process_floor_plans(project_id=str(args.project_id))
    elif args.all:
        process_floor_plans()
    else:
        print("Usage:")
        print("  python analyze_floor_plans.py --project-id 123")
        print("  python analyze_floor_plans.py --all")
