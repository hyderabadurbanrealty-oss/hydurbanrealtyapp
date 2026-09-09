# Floor Plan Analysis Feature - Setup Guide

## Overview

Offline batch processing system that analyzes floor plans using AI and stores insights in the database for display on your website.

**Features:**
- ✅ Flow/Circulation analysis
- ✅ Privacy scoring
- ✅ Natural light assessment
- ✅ Space efficiency metrics
- ✅ Vastu compliance (Indian market)
- ✅ Room-by-room findings
- ✅ Actionable recommendations

## Architecture

```
Local Python Script → Download Floor Plans → AI Analysis → Store in Database → Display on Website
```

## Setup Options

### Option 1: OpenAI GPT-4 Vision (Recommended)

**Pros:** Best quality, easy setup, no local GPU needed  
**Cons:** Costs ~₹5-10 per analysis  
**Best for:** High-quality analysis, low volume (<1000/month)

```bash
# Install dependencies
pip install openai psycopg2-binary requests

# Set API key
set OPENAI_API_KEY=sk-your-key-here  # Windows
export OPENAI_API_KEY=sk-your-key-here  # Linux/Mac

# Edit analyze_floor_plans.py
USE_LOCAL_LLM = False  # Line 28
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # Line 27
```

### Option 2: Local LLM (Ollama + Llama 3.2 Vision)

**Pros:** Free, unlimited usage, privacy  
**Cons:** Requires good GPU (8GB+ VRAM), slightly lower quality  
**Best for:** High volume, cost-sensitive, data privacy

```bash
# 1. Install Ollama
# Download from: https://ollama.com/download

# 2. Pull vision model
ollama pull llama3.2-vision

# 3. Verify it's running
ollama list

# 4. Install Python dependencies
pip install psycopg2-binary requests

# 5. Edit analyze_floor_plans.py
USE_LOCAL_LLM = True  # Line 28
```

### Option 3: Basic Rule-Based (Fallback)

**Pros:** Works without AI, no cost, no setup  
**Cons:** Limited insights, no real analysis  
**Best for:** Testing, placeholder

Just run the script without OpenAI key or Ollama. It will use basic heuristics.

## Database Setup

```bash
# Run SQL migration
psql -h aws-0-ap-northeast-1.pooler.supabase.com \
     -p 5432 \
     -U postgres.qjgwnbszmojzgwmafvuc \
     -d postgres \
     -f backend/create_floor_plan_analysis_table.sql

# Or use pgAdmin / Supabase SQL Editor
```

## Usage

### Analyze Specific Project

```bash
cd backend
python analyze_floor_plans.py --project-id 123
```

### Analyze All Unprocessed Floor Plans (Batch)

```bash
python analyze_floor_plans.py --all
```

### Re-analyze Existing (Update Database)

Delete existing analysis first, then run again:

```sql
DELETE FROM floor_plan_analysis WHERE project_id = 123;
```

```bash
python analyze_floor_plans.py --project-id 123
```

## What It Does

1. **Finds Floor Plans**: Queries `project_media` table for `media_type = 'floorplan'`
2. **Downloads Images**: Downloads from Supabase storage to temp folder
3. **AI Analysis**: Sends to GPT-4 Vision or local LLM with structured prompt
4. **Extracts Insights**: Parses JSON response with scores, findings, recommendations
5. **Stores Results**: Saves to `floor_plan_analysis` table
6. **Cleanup**: Deletes temp files

## Output Format

```json
{
  "overall_score": 78,
  "livability_scores": {
    "flow": 80,
    "privacy": 65,
    "light": 85,
    "space_efficiency": 75,
    "storage": 70,
    "vastu": 60
  },
  "findings": [
    {
      "category": "privacy",
      "severity": "warning",
      "title": "Bedroom visible from entrance",
      "description": "Master bedroom door directly visible when entering...",
      "location": "Master Bedroom"
    }
  ],
  "highlights": [
    "Excellent cross ventilation",
    "Well-sized living room"
  ],
  "concerns": [
    "Limited storage in kitchen",
    "Bathroom facing east (Vastu concern)"
  ],
  "vastu_analysis": {
    "main_entrance": "North-East facing (Excellent)",
    "kitchen": "South-East (Ideal)",
    "master_bedroom": "South-West (Good)",
    "overall_compliance": "75%"
  },
  "recommendations": [
    "Consider privacy screen at entrance",
    "Add modular storage in kitchen"
  ]
}
```

## Display on Website

### Backend API Endpoint (Add to .NET Controllers)

```csharp
// Controllers/ProjectController.cs

[HttpGet("{id}/floor-plan-analysis")]
public async Task<IActionResult> GetFloorPlanAnalysis(int id)
{
    var analysis = await _context.FloorPlanAnalysis
        .Where(a => a.ProjectId == id)
        .OrderByDescending(a => a.AnalyzedAt)
        .FirstOrDefaultAsync();
        
    if (analysis == null)
        return NotFound(new { message = "No analysis available" });
        
    return Ok(analysis);
}
```

### Frontend Display (Add to Property Detail Page)

```typescript
// property-detail.component.ts

floorPlanAnalysis: any = null;

loadFloorPlanAnalysis() {
  this.service.getFloorPlanAnalysis(this.property.id).subscribe({
    next: (analysis) => {
      this.floorPlanAnalysis = analysis;
    }
  });
}
```

```html
<!-- property-detail.component.html -->

<div class="floor-plan-analysis" *ngIf="floorPlanAnalysis">
  <h3>Floor Plan Insights</h3>
  
  <!-- Overall Score -->
  <div class="score-badge" [class.score-high]="floorPlanAnalysis.overall_score >= 70">
    {{ floorPlanAnalysis.overall_score }}/100
    <span>Livability Score</span>
  </div>
  
  <!-- Score Breakdown -->
  <div class="score-grid">
    <div class="score-item">
      <span class="label">Flow</span>
      <span class="value">{{ floorPlanAnalysis.flow_score }}/100</span>
    </div>
    <div class="score-item">
      <span class="label">Privacy</span>
      <span class="value">{{ floorPlanAnalysis.privacy_score }}/100</span>
    </div>
    <div class="score-item">
      <span class="label">Vastu</span>
      <span class="value">{{ floorPlanAnalysis.vastu_score }}/100</span>
    </div>
  </div>
  
  <!-- Highlights -->
  <div class="highlights">
    <h4>✨ Highlights</h4>
    <ul>
      <li *ngFor="let h of floorPlanAnalysis.highlights">{{ h }}</li>
    </ul>
  </div>
  
  <!-- Concerns -->
  <div class="concerns" *ngIf="floorPlanAnalysis.concerns?.length">
    <h4>⚠️ Points to Consider</h4>
    <ul>
      <li *ngFor="let c of floorPlanAnalysis.concerns">{{ c }}</li>
    </ul>
  </div>
  
  <!-- Vastu Analysis -->
  <div class="vastu-analysis" *ngIf="floorPlanAnalysis.vastu_analysis">
    <h4>🕉️ Vastu Compliance</h4>
    <p>{{ floorPlanAnalysis.vastu_analysis.overall_compliance }}</p>
  </div>
</div>
```

## Cost Estimation

### OpenAI GPT-4 Vision
- **Per analysis**: ~$0.05-0.10 (₹4-8)
- **100 properties**: ~₹400-800
- **1000 properties**: ~₹4,000-8,000

### Local LLM (Ollama)
- **Setup cost**: Free (requires existing PC/server)
- **Per analysis**: ₹0 (electricity only)
- **Unlimited analyses**

## Automation

### Run Daily (Windows Task Scheduler)

```bash
# Create batch file: analyze_daily.bat
cd C:\Bilva\hydurbanrealtyapp\backend
python analyze_floor_plans.py --all
```

Schedule in Task Scheduler:
- Trigger: Daily at 2 AM
- Action: Run `analyze_daily.bat`

### Run on New Project Upload

Add to your project creation flow:

```python
# After uploading floor plan to Supabase
import subprocess
subprocess.run(['python', 'analyze_floor_plans.py', '--project-id', str(project_id)])
```

## Troubleshooting

### "Module not found"
```bash
pip install -r backend/requirements_floor_plan.txt
```

### "OpenAI API key not found"
```bash
set OPENAI_API_KEY=sk-your-key  # Windows
export OPENAI_API_KEY=sk-your-key  # Linux/Mac
```

### "Connection to localhost:11434 refused"
```bash
# Start Ollama
ollama serve

# In another terminal
ollama pull llama3.2-vision
```

### "Table floor_plan_analysis does not exist"
```bash
psql -f backend/create_floor_plan_analysis_table.sql
```

## Next Steps

1. **Test with Sample Project**:
   ```bash
   python analyze_floor_plans.py --project-id 1
   ```

2. **Check Results in Database**:
   ```sql
   SELECT * FROM floor_plan_analysis LIMIT 5;
   ```

3. **Add API Endpoint** in .NET backend

4. **Display on Frontend** in property-detail page

5. **Batch Process All**:
   ```bash
   python analyze_floor_plans.py --all
   ```

6. **Monitor Quality**: Review first 10-20 analyses, adjust prompt if needed

## Advanced: Custom Training (Future)

If you want even better results for Indian floor plans:

1. Collect 500+ analyzed floor plans
2. Fine-tune GPT-4 Vision or train custom model
3. Cost: ₹50,000-2,00,000 for training
4. Result: 10-20% better accuracy

## Support

For issues or questions:
- Check logs in console output
- Review `temp_floor_plans/` folder for downloaded images
- Verify database connection with `psql`
- Test AI with simple prompt first
