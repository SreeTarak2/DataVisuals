#!/usr/bin/env python3
"""
DataSage Flow Diagram Generator
Creates comprehensive visual diagrams for the DataSage project
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
import matplotlib.patches as mpatches

# Set up the style
plt.style.use('default')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['figure.dpi'] = 300

# Color scheme
COLORS = {
    'primary': '#3B82F6',
    'secondary': '#10B981', 
    'accent': '#F59E0B',
    'danger': '#EF4444',
    'purple': '#8B5CF6',
    'gray': '#6B7280',
    'light_gray': '#F3F4F6',
    'dark_gray': '#374151',
    'white': '#FFFFFF'
}

def create_images_directory():
    """Create images directory if it doesn't exist"""
    if not os.path.exists('images'):
        os.makedirs('images')
        print("Created images directory")

def create_system_architecture():
    """Create complete system architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(5, 9.5, 'DataSage System Architecture', 
            fontsize=20, fontweight='bold', ha='center')
    
    # Frontend Layer
    frontend_box = FancyBboxPatch((0.5, 7), 4, 1.5, 
                                 boxstyle="round,pad=0.1", 
                                 facecolor=COLORS['light_gray'], 
                                 edgecolor=COLORS['primary'], 
                                 linewidth=2)
    ax.add_patch(frontend_box)
    ax.text(2.5, 7.75, 'Frontend Layer (React + Vite)', 
            fontsize=14, fontweight='bold', ha='center')
    
    # Frontend components
    components = ['Authentication UI', 'Dashboard', 'Dataset Management', 'AI Builder', 'Charts']
    for i, comp in enumerate(components):
        x = 1 + (i % 3) * 1.2
        y = 7.2 + (i // 3) * 0.3
        ax.text(x, y, comp, fontsize=9, ha='center')
    
    # Backend Layer
    backend_box = FancyBboxPatch((5.5, 7), 4, 1.5, 
                                boxstyle="round,pad=0.1", 
                                facecolor=COLORS['light_gray'], 
                                edgecolor=COLORS['secondary'], 
                                linewidth=2)
    ax.add_patch(backend_box)
    ax.text(7.5, 7.75, 'Backend Layer (FastAPI + Python)', 
            fontsize=14, fontweight='bold', ha='center')
    
    # Backend components
    backend_components = ['API Gateway', 'Auth Service', 'Dataset Service', 'AI Service', 'File Storage']
    for i, comp in enumerate(backend_components):
        x = 6 + (i % 3) * 1.2
        y = 7.2 + (i // 3) * 0.3
        ax.text(x, y, comp, fontsize=9, ha='center')
    
    # Data Layer
    data_box = FancyBboxPatch((2, 4.5), 6, 1.5, 
                             boxstyle="round,pad=0.1", 
                             facecolor=COLORS['light_gray'], 
                             edgecolor=COLORS['purple'], 
                             linewidth=2)
    ax.add_patch(data_box)
    ax.text(5, 5.25, 'Data Layer (MongoDB + File System)', 
            fontsize=14, fontweight='bold', ha='center')
    
    # Data components
    data_components = ['MongoDB Database', 'File Storage', 'Metadata Management', 'Data Processing']
    for i, comp in enumerate(data_components):
        x = 2.5 + i * 1.5
        y = 4.7
        ax.text(x, y, comp, fontsize=9, ha='center')
    
    # AI Layer
    ai_box = FancyBboxPatch((2, 2.5), 6, 1.5, 
                           boxstyle="round,pad=0.1", 
                           facecolor=COLORS['light_gray'], 
                           edgecolor=COLORS['accent'], 
                           linewidth=2)
    ax.add_patch(ai_box)
    ax.text(5, 3.25, 'AI Processing Layer', 
            fontsize=14, fontweight='bold', ha='center')
    
    # AI components
    ai_components = ['Pattern Recognition', 'Statistical Analysis', 'NLP Processing', 'Recommendation Engine']
    for i, comp in enumerate(ai_components):
        x = 2.5 + i * 1.5
        y = 2.7
        ax.text(x, y, comp, fontsize=9, ha='center')
    
    # Arrows showing data flow
    # Frontend to Backend
    arrow1 = FancyArrowPatch((4.5, 7.5), (5.5, 7.5), 
                            arrowstyle='->', mutation_scale=20, 
                            color=COLORS['primary'], linewidth=2)
    ax.add_patch(arrow1)
    ax.text(5, 7.8, 'API Calls', fontsize=8, ha='center')
    
    # Backend to Data
    arrow2 = FancyArrowPatch((7.5, 7), (5, 6), 
                            arrowstyle='->', mutation_scale=20, 
                            color=COLORS['secondary'], linewidth=2)
    ax.add_patch(arrow2)
    ax.text(6.2, 6.5, 'Data Storage', fontsize=8, ha='center')
    
    # Backend to AI
    arrow3 = FancyArrowPatch((7.5, 7), (5, 4), 
                            arrowstyle='->', mutation_scale=20, 
                            color=COLORS['accent'], linewidth=2)
    ax.add_patch(arrow3)
    ax.text(6.2, 5.5, 'AI Processing', fontsize=8, ha='center')
    
    # AI to Data
    arrow4 = FancyArrowPatch((5, 2.5), (5, 4.5), 
                            arrowstyle='->', mutation_scale=20, 
                            color=COLORS['purple'], linewidth=2)
    ax.add_patch(arrow4)
    ax.text(5.3, 3.5, 'Analysis Results', fontsize=8, ha='center')
    
    plt.tight_layout()
    plt.savefig('images/system-architecture.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created system-architecture.png")

def create_auth_flow():
    """Create user authentication flow diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(5, 7.5, 'User Authentication Flow', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Flow steps
    steps = [
        (2, 6.5, 'User Opens App', COLORS['primary']),
        (5, 6.5, 'Login/Register', COLORS['secondary']),
        (8, 6.5, 'Enter Credentials', COLORS['accent']),
        (2, 5, 'Validate Credentials', COLORS['purple']),
        (5, 5, 'Generate JWT Token', COLORS['primary']),
        (8, 5, 'Store Token', COLORS['secondary']),
        (5, 3.5, 'Redirect to Dashboard', COLORS['accent']),
        (5, 2, 'Load User Data', COLORS['purple'])
    ]
    
    # Draw steps
    for i, (x, y, text, color) in enumerate(steps):
        # Draw circle
        circle = Circle((x, y), 0.3, facecolor=color, edgecolor='black', linewidth=1)
        ax.add_patch(circle)
        ax.text(x, y, str(i+1), fontsize=10, fontweight='bold', ha='center', va='center', color='white')
        
        # Draw text
        ax.text(x, y-0.8, text, fontsize=10, ha='center', va='center')
    
    # Draw arrows
    arrows = [
        ((2, 6.2), (5, 6.2)),
        ((5, 6.2), (8, 6.2)),
        ((8, 6.2), (2, 5.3)),
        ((2, 4.7), (5, 5.3)),
        ((5, 4.7), (8, 5.3)),
        ((8, 4.7), (5, 3.8)),
        ((5, 3.2), (5, 2.3))
    ]
    
    for start, end in arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=15, color=COLORS['dark_gray'], linewidth=2)
        ax.add_patch(arrow)
    
    # Decision diamond
    diamond = patches.FancyBboxPatch((4, 4.2), 2, 0.6, 
                                    boxstyle="round,pad=0.1", 
                                    facecolor=COLORS['light_gray'], 
                                    edgecolor=COLORS['danger'], 
                                    linewidth=2)
    ax.add_patch(diamond)
    ax.text(5, 4.5, 'Valid?', fontsize=10, ha='center', va='center')
    
    plt.tight_layout()
    plt.savefig('images/auth-flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created auth-flow.png")

def create_upload_flow():
    """Create dataset upload flow diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(6, 9.5, 'Dataset Upload Flow', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Flow steps
    steps = [
        (2, 8, 'User Clicks Upload', COLORS['primary']),
        (4, 8, 'Open Upload Modal', COLORS['secondary']),
        (6, 8, 'Select File', COLORS['accent']),
        (8, 8, 'Validate File', COLORS['purple']),
        (10, 8, 'Show Preview', COLORS['primary']),
        (2, 6, 'Enter Dataset Name', COLORS['secondary']),
        (4, 6, 'Click Upload', COLORS['accent']),
        (6, 6, 'POST /api/upload', COLORS['purple']),
        (8, 6, 'Save to Storage', COLORS['primary']),
        (10, 6, 'Generate Metadata', COLORS['secondary']),
        (2, 4, 'Store in MongoDB', COLORS['accent']),
        (4, 4, 'AI Analysis', COLORS['purple']),
        (6, 4, 'Return Response', COLORS['primary']),
        (8, 4, 'Update UI', COLORS['secondary']),
        (10, 4, 'Close Modal', COLORS['accent'])
    ]
    
    # Draw steps
    for i, (x, y, text, color) in enumerate(steps):
        # Draw rectangle
        rect = FancyBboxPatch((x-0.4, y-0.3), 0.8, 0.6, 
                             boxstyle="round,pad=0.05", 
                             facecolor=color, 
                             edgecolor='black', 
                             linewidth=1)
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=8, ha='center', va='center', 
                color='white', fontweight='bold')
    
    # Draw arrows
    arrows = [
        ((2, 7.7), (4, 7.7)),
        ((4, 7.7), (6, 7.7)),
        ((6, 7.7), (8, 7.7)),
        ((8, 7.7), (10, 7.7)),
        ((10, 7.7), (2, 6.3)),
        ((2, 5.7), (4, 5.7)),
        ((4, 5.7), (6, 5.7)),
        ((6, 5.7), (8, 5.7)),
        ((8, 5.7), (10, 5.7)),
        ((10, 5.7), (2, 4.3)),
        ((2, 3.7), (4, 3.7)),
        ((4, 3.7), (6, 3.7)),
        ((6, 3.7), (8, 3.7)),
        ((8, 3.7), (10, 3.7))
    ]
    
    for start, end in arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=12, color=COLORS['dark_gray'], linewidth=1.5)
        ax.add_patch(arrow)
    
    # Error handling
    error_box = FancyBboxPatch((8.5, 7), 2, 0.5, 
                              boxstyle="round,pad=0.05", 
                              facecolor=COLORS['danger'], 
                              edgecolor='black', 
                              linewidth=1)
    ax.add_patch(error_box)
    ax.text(9.5, 7.25, 'Show Error', fontsize=8, ha='center', va='center', 
            color='white', fontweight='bold')
    
    # Error arrow
    error_arrow = FancyArrowPatch((8, 7.7), (8.5, 7.3), 
                                 arrowstyle='->', 
                                 mutation_scale=12, color=COLORS['danger'], linewidth=1.5)
    ax.add_patch(error_arrow)
    
    plt.tight_layout()
    plt.savefig('images/upload-flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created upload-flow.png")

def create_ai_visualization_flow():
    """Create AI visualization builder flow diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'AI Visualization Builder Flow', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Main flow
    main_steps = [
        (2, 8, 'Click AI Builder', COLORS['purple']),
        (4, 8, 'Select Dataset', COLORS['primary']),
        (6, 8, 'Load Metadata', COLORS['secondary']),
        (8, 8, 'AI Analysis', COLORS['accent']),
        (10, 8, 'Generate Recommendations', COLORS['purple']),
        (12, 8, 'Display Suggestions', COLORS['primary'])
    ]
    
    # AI Processing steps
    ai_steps = [
        (2, 6, 'Pattern Recognition', COLORS['accent']),
        (4, 6, 'Statistical Analysis', COLORS['secondary']),
        (6, 6, 'Field Recommendations', COLORS['purple']),
        (8, 6, 'Chart Suggestions', COLORS['primary']),
        (10, 6, 'Confidence Scoring', COLORS['accent']),
        (12, 6, 'UI Presentation', COLORS['secondary'])
    ]
    
    # User Interaction steps
    user_steps = [
        (2, 4, 'Select Recommendation', COLORS['purple']),
        (4, 4, 'Generate Chart Data', COLORS['primary']),
        (6, 4, 'Create Plotly Chart', COLORS['secondary']),
        (8, 4, 'Display Interactive Chart', COLORS['accent']),
        (10, 4, 'Enable Drill-down', COLORS['purple']),
        (12, 4, 'Save Configuration', COLORS['primary'])
    ]
    
    # Natural Language steps
    nl_steps = [
        (2, 2, 'User Types Query', COLORS['accent']),
        (4, 2, 'NLP Processing', COLORS['purple']),
        (6, 2, 'Intent Recognition', COLORS['primary']),
        (8, 2, 'Generate Response', COLORS['secondary']),
        (10, 2, 'Show Follow-ups', COLORS['accent']),
        (12, 2, 'Update UI', COLORS['purple'])
    ]
    
    # Draw all steps
    all_steps = main_steps + ai_steps + user_steps + nl_steps
    for i, (x, y, text, color) in enumerate(all_steps):
        rect = FancyBboxPatch((x-0.5, y-0.3), 1, 0.6, 
                             boxstyle="round,pad=0.05", 
                             facecolor=color, 
                             edgecolor='black', 
                             linewidth=1)
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=7, ha='center', va='center', 
                color='white', fontweight='bold')
    
    # Draw arrows between main flow
    main_arrows = [
        ((2, 7.7), (4, 7.7)),
        ((4, 7.7), (6, 7.7)),
        ((6, 7.7), (8, 7.7)),
        ((8, 7.7), (10, 7.7)),
        ((10, 7.7), (12, 7.7))
    ]
    
    for start, end in main_arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=15, color=COLORS['dark_gray'], linewidth=2)
        ax.add_patch(arrow)
    
    # Draw vertical arrows
    vert_arrows = [
        ((6, 7.7), (6, 6.3)),  # Load Metadata to Statistical Analysis
        ((8, 7.7), (8, 6.3)),  # AI Analysis to Chart Suggestions
        ((10, 7.7), (10, 6.3)), # Generate Recommendations to Confidence Scoring
        ((12, 7.7), (12, 6.3)), # Display Suggestions to UI Presentation
        ((2, 5.7), (2, 4.3)),  # Pattern Recognition to Select Recommendation
        ((4, 5.7), (4, 4.3)),  # Statistical Analysis to Generate Chart Data
        ((6, 5.7), (6, 4.3)),  # Field Recommendations to Create Plotly Chart
        ((8, 5.7), (8, 4.3)),  # Chart Suggestions to Display Interactive Chart
        ((10, 5.7), (10, 4.3)), # Confidence Scoring to Enable Drill-down
        ((12, 5.7), (12, 4.3)), # UI Presentation to Save Configuration
        ((2, 3.7), (2, 2.3)),  # Select Recommendation to User Types Query
        ((4, 3.7), (4, 2.3)),  # Generate Chart Data to NLP Processing
        ((6, 3.7), (6, 2.3)),  # Create Plotly Chart to Intent Recognition
        ((8, 3.7), (8, 2.3)),  # Display Interactive Chart to Generate Response
        ((10, 3.7), (10, 2.3)), # Enable Drill-down to Show Follow-ups
        ((12, 3.7), (12, 2.3))  # Save Configuration to Update UI
    ]
    
    for start, end in vert_arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=10, color=COLORS['dark_gray'], linewidth=1)
        ax.add_patch(arrow)
    
    # Add labels
    ax.text(1, 7, 'Main Flow', fontsize=12, fontweight='bold', rotation=90)
    ax.text(1, 5, 'AI Processing', fontsize=12, fontweight='bold', rotation=90)
    ax.text(1, 3, 'User Interaction', fontsize=12, fontweight='bold', rotation=90)
    ax.text(1, 1, 'Natural Language', fontsize=12, fontweight='bold', rotation=90)
    
    plt.tight_layout()
    plt.savefig('images/ai-visualization-flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created ai-visualization-flow.png")

def create_data_processing_flow():
    """Create data processing pipeline diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(6, 7.5, 'Data Processing Pipeline', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Processing steps
    steps = [
        (2, 6, 'File Upload', COLORS['primary']),
        (4, 6, 'Validation', COLORS['secondary']),
        (6, 6, 'Type Detection', COLORS['accent']),
        (8, 6, 'Metadata Generation', COLORS['purple']),
        (10, 6, 'AI Analysis', COLORS['primary']),
        (2, 4, 'MongoDB Storage', COLORS['secondary']),
        (4, 4, 'File Storage', COLORS['accent']),
        (6, 4, 'Index Creation', COLORS['purple']),
        (8, 4, 'Cache Update', COLORS['primary']),
        (10, 4, 'API Response', COLORS['secondary']),
        (6, 2, 'Frontend Update', COLORS['accent'])
    ]
    
    # Draw steps
    for i, (x, y, text, color) in enumerate(steps):
        rect = FancyBboxPatch((x-0.5, y-0.3), 1, 0.6, 
                             boxstyle="round,pad=0.05", 
                             facecolor=color, 
                             edgecolor='black', 
                             linewidth=1)
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=8, ha='center', va='center', 
                color='white', fontweight='bold')
    
    # Draw arrows
    arrows = [
        ((2, 5.7), (4, 5.7)),
        ((4, 5.7), (6, 5.7)),
        ((6, 5.7), (8, 5.7)),
        ((8, 5.7), (10, 5.7)),
        ((10, 5.7), (2, 4.3)),
        ((2, 3.7), (4, 3.7)),
        ((4, 3.7), (6, 3.7)),
        ((6, 3.7), (8, 3.7)),
        ((8, 3.7), (10, 3.7)),
        ((10, 3.7), (6, 2.3))
    ]
    
    for start, end in arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=15, color=COLORS['dark_gray'], linewidth=2)
        ax.add_patch(arrow)
    
    # Add parallel processing indicators
    ax.text(6, 5.2, 'Parallel Processing', fontsize=10, ha='center', 
            bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS['light_gray']))
    
    plt.tight_layout()
    plt.savefig('images/data-processing-flow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created data-processing-flow.png")

def create_user_journey():
    """Create complete user journey diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(7, 7.5, 'Complete User Journey', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Journey steps
    journey_steps = [
        (1, 6, 'Landing Page', COLORS['primary']),
        (3, 6, 'Registration', COLORS['secondary']),
        (5, 6, 'Email Verification', COLORS['accent']),
        (7, 6, 'Login', COLORS['purple']),
        (9, 6, 'Dashboard', COLORS['primary']),
        (11, 6, 'Upload Dataset', COLORS['secondary']),
        (13, 6, 'AI Analysis', COLORS['accent']),
        (1, 4, 'Chart Generation', COLORS['purple']),
        (3, 4, 'Interactive Visualization', COLORS['primary']),
        (5, 4, 'Drill-down Exploration', COLORS['secondary']),
        (7, 4, 'Export/Share', COLORS['accent']),
        (9, 4, 'Save Insights', COLORS['purple']),
        (11, 4, 'Create Reports', COLORS['primary']),
        (13, 4, 'Team Collaboration', COLORS['secondary']),
        (7, 2, 'Advanced Analytics', COLORS['accent']),
        (7, 1, 'Business Intelligence', COLORS['purple'])
    ]
    
    # Draw steps
    for i, (x, y, text, color) in enumerate(journey_steps):
        if y == 6:  # Top row
            rect = FancyBboxPatch((x-0.4, y-0.3), 0.8, 0.6, 
                                 boxstyle="round,pad=0.05", 
                                 facecolor=color, 
                                 edgecolor='black', 
                                 linewidth=1)
        elif y == 4:  # Middle row
            rect = FancyBboxPatch((x-0.4, y-0.3), 0.8, 0.6, 
                                 boxstyle="round,pad=0.05", 
                                 facecolor=color, 
                                 edgecolor='black', 
                                 linewidth=1)
        else:  # Bottom rows
            rect = FancyBboxPatch((x-0.6, y-0.3), 1.2, 0.6, 
                                 boxstyle="round,pad=0.05", 
                                 facecolor=color, 
                                 edgecolor='black', 
                                 linewidth=1)
        
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=7, ha='center', va='center', 
                color='white', fontweight='bold')
    
    # Draw arrows
    arrows = [
        ((1, 5.7), (3, 5.7)),
        ((3, 5.7), (5, 5.7)),
        ((5, 5.7), (7, 5.7)),
        ((7, 5.7), (9, 5.7)),
        ((9, 5.7), (11, 5.7)),
        ((11, 5.7), (13, 5.7)),
        ((13, 5.7), (1, 4.3)),
        ((1, 3.7), (3, 3.7)),
        ((3, 3.7), (5, 3.7)),
        ((5, 3.7), (7, 3.7)),
        ((7, 3.7), (9, 3.7)),
        ((9, 3.7), (11, 3.7)),
        ((11, 3.7), (13, 3.7)),
        ((13, 3.7), (7, 2.3)),
        ((7, 1.7), (7, 1.3))
    ]
    
    for start, end in arrows:
        arrow = FancyArrowPatch(start, end, arrowstyle='->', 
                               mutation_scale=12, color=COLORS['dark_gray'], linewidth=1.5)
        ax.add_patch(arrow)
    
    # Add phase labels
    ax.text(2, 6.5, 'Onboarding', fontsize=12, fontweight='bold', ha='center')
    ax.text(6, 6.5, 'Data Upload', fontsize=12, fontweight='bold', ha='center')
    ax.text(10, 6.5, 'AI Analysis', fontsize=12, fontweight='bold', ha='center')
    ax.text(2, 4.5, 'Visualization', fontsize=12, fontweight='bold', ha='center')
    ax.text(6, 4.5, 'Exploration', fontsize=12, fontweight='bold', ha='center')
    ax.text(10, 4.5, 'Collaboration', fontsize=12, fontweight='bold', ha='center')
    ax.text(7, 2.5, 'Advanced Features', fontsize=12, fontweight='bold', ha='center')
    ax.text(7, 0.5, 'Business Value', fontsize=12, fontweight='bold', ha='center')
    
    plt.tight_layout()
    plt.savefig('images/user-journey.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created user-journey.png")

def main():
    """Generate all diagrams"""
    print("Creating DataSage Flow Diagrams...")
    create_images_directory()
    
    # Generate all diagrams
    create_system_architecture()
    create_auth_flow()
    create_upload_flow()
    create_ai_visualization_flow()
    create_data_processing_flow()
    create_user_journey()
    
    print("\nAll diagrams created successfully!")
    print("Images saved in the 'images' directory")

if __name__ == "__main__":
    main()
