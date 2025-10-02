# Aspect Category Management Guide

## Overview
This system allows admins to define hierarchical aspect categories for customer review analysis.

## Hierarchy Structure

```
Category (e.g., Electronics, Food, Hotels)
  └── Aspect (e.g., Camera, Battery, Service)
        ├── Name: Display name of the aspect
        ├── Description: What this aspect covers
        ├── Weightage: Importance (1-5 scale, 5 = very important)
        └── Keywords: Comma-separated words/phrases for matching
```

## How to Use

### 1. Access the Management Page
- Login as Admin
- Navigate to **"Manage Aspect Categories"**

### 2. Create a New Category with Aspects

#### Form Fields:

**Category Information:**
- **Category Name** (required): e.g., "Electronics", "Food", "Hotels"
- **Category Description** (optional): Brief explanation

**Aspects (at least one):**
For each aspect, provide:
- **Aspect Name** (required): e.g., "Camera", "Battery", "Service"
- **Description** (optional): What this aspect covers
- **Weightage** (required, 1-5): Importance level (default: 3)
- **Keywords** (required): Comma-separated matching terms

#### Example: Electronics Category

```
Category Name: Electronics
Description: Consumer electronic devices like smartphones, laptops, etc.

Aspect 1:
  Name: Camera
  Description: Quality and performance of device camera
  Weightage: 4
  Keywords: photo, image, pictures, camera, shoot, video, lens

Aspect 2:
  Name: Battery
  Description: Battery life, charging speed, and power efficiency
  Weightage: 5
  Keywords: battery, charge, power, drain, backup, life, charging

Aspect 3:
  Name: Display
  Description: Screen quality, brightness, and resolution
  Weightage: 4
  Keywords: screen, display, brightness, resolution, colors, panel
```

### 3. Add More Aspects Dynamically
- Click **"+ Add Another Aspect"** to add more aspects to the category
- Click **"Remove"** to delete an aspect before submission

### 4. Submit
- Click **"Create Category with Aspects"**
- The system will:
  - Create the category
  - Add all aspects with their keywords
  - Reload the NLP processor to use new categories immediately

### 5. View Existing Categories
- All categories are listed below the form
- Each category shows its aspects in a table with:
  - Name
  - Description
  - Weightage
  - Keywords
  - Actions (Edit/Delete)

### 6. Add Aspects to Existing Categories
- Under each existing category, use the inline form to add new aspects

## Database Schema

### Category Table
- `id`: Primary key
- `name`: Unique category name
- `description`: Optional description

### Aspect Table
- `id`: Primary key
- `name`: Aspect name
- `description`: Optional description
- `weightage`: Float (1.0-5.0)
- `category_id`: Foreign key to Category

### AspectKeyword Table
- `id`: Primary key
- `keyword`: Matching keyword
- `aspect_id`: Foreign key to Aspect

## How It Works in Review Analysis

1. **Review Submission**: User uploads a review
2. **NLP Processing**: System extracts noun phrases
3. **Keyword Matching**: Extracted phrases are matched against keywords
4. **Aspect Assignment**: Matched phrases are tagged with the corresponding aspect
5. **Sentiment Analysis**: Each aspect gets a sentiment score (Positive/Negative/Neutral)
6. **Aggregation**: Results are grouped by category and aspect for reporting

## Best Practices

### Keyword Selection
- Include variations: "photo", "photograph", "picture"
- Include common misspellings if relevant
- Use lowercase (system normalizes automatically)
- Be specific but comprehensive

### Weightage Guidelines
- **5**: Critical aspects (e.g., Battery for phones, Taste for food)
- **4**: Very important (e.g., Camera, Service)
- **3**: Moderately important (e.g., Design, Packaging)
- **2**: Nice to have (e.g., Accessories)
- **1**: Minor aspects (e.g., Box quality)

### Category Organization
- Keep categories broad (Electronics, not "Smartphones")
- Use aspects for specificity (Camera, Battery, not "iPhone Camera")
- Avoid overlapping keywords between aspects in same category

## Example Categories

### Electronics (Mobile Phones)
- Camera (weightage: 4)
- Battery (weightage: 5)
- Display (weightage: 4)
- Performance (weightage: 5)
- Build Quality (weightage: 3)
- Price (weightage: 4)

### Food (Restaurants)
- Taste (weightage: 5)
- Service (weightage: 4)
- Ambiance (weightage: 3)
- Hygiene (weightage: 5)
- Portion Size (weightage: 3)
- Price (weightage: 4)

### Hotels
- Cleanliness (weightage: 5)
- Service (weightage: 5)
- Location (weightage: 4)
- Amenities (weightage: 3)
- Food (weightage: 4)
- Value for Money (weightage: 4)

## Troubleshooting

### Category not appearing in analysis
- Ensure NLP processor is initialized (check logs)
- Verify keywords are added to aspects
- Check that aspects are linked to the category

### Keywords not matching
- Use lowercase
- Avoid special characters
- Include common variations
- Check for typos in keywords

### Aspects not showing in results
- Ensure weightage is set (required field)
- Verify at least one keyword exists
- Check database relationships (category_id, aspect_id)
