#!/usr/bin/env python3
"""
Extract JavaScript from HTML templates and save to static files.
This helps with the refactoring to separate CSS/JS from inline code.
"""
import re
import os
from pathlib import Path

def extract_js_from_template(html_file):
    """Extract JavaScript content from an HTML template file."""
    with open(html_file, 'r') as f:
        content = f.read()
    
    # Find all script blocks in {% block extra_scripts %}...{% endblock %}
    # Or inline <script>...</script> tags
    matches = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
    
    if matches:
        # Filter out empty scripts
        scripts = [m.strip() for m in matches if m.strip() and not m.strip().startswith('//')]
        return '\n\n'.join(scripts)
    return None

def extract_css_from_template(html_file):
    """Extract CSS content from an HTML template file."""
    with open(html_file, 'r') as f:
        content = f.read()
    
    # Find all style blocks in {% block extra_styles %}...{% endblock %}
    # Or inline <style>...</style> tags
    matches = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    
    if matches:
        # Filter out empty styles
        styles = [m.strip() for m in matches if m.strip()]
        return '\n\n'.join(styles)
    return None

if __name__ == '__main__':
    templates_dir = Path('phone_migration/web_templates')
    static_js_dir = Path('phone_migration/static/js')
    static_css_dir = Path('phone_migration/static/css')
    
    # Templates to process
    templates = {
        'dashboard.html': 'dashboard',
        'profiles.html': 'profiles',
        'rules.html': 'rules',
        'history.html': 'history',
        'run.html': 'run',
    }
    
    print("Extracting JavaScript and CSS from templates...")
    
    for html_file, name in templates.items():
        html_path = templates_dir / html_file
        
        if not html_path.exists():
            print(f"Warning: {html_path} not found, skipping")
            continue
        
        # Extract JS
        js_content = extract_js_from_template(html_path)
        if js_content:
            js_file = static_js_dir / f'{name}.js'
            print(f"  ✓ Created {js_file}")
            with open(js_file, 'w') as f:
                f.write(js_content)
        
        # Extract CSS
        css_content = extract_css_from_template(html_path)
        if css_content:
            css_file = static_css_dir / f'{name}.css'
            print(f"  ✓ Created {css_file}")
            with open(css_file, 'w') as f:
                f.write(css_content)
    
    print("\nDone! JavaScript and CSS have been extracted.")
    print("\nNext steps:")
    print("1. Update each HTML template to link to external CSS/JS files")
    print("2. Remove inline <style> and <script> blocks from templates")
    print("3. Test all pages in the browser")
