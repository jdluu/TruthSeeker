from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import re

def generate_pdf(history, filename):
    """Generate a PDF from the query history."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()

    # Define custom styles
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.darkblue,
        alignment=1,  # Center alignment
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        name='HeadingStyle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.blue,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        name='NormalStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=14,
        fontName='Helvetica'
    )
    
    reference_style = ParagraphStyle(
        name='ReferenceStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        fontName='Times-Italic',
        textColor=colors.black
    )

    story = []

    # Add title
    story.append(Paragraph("<b>AI Fact Checker History</b>", title_style))
    story.append(Spacer(1, 0.5 * inch))

    for i, query in enumerate(history):
        story.append(Paragraph(f"<b>Query {i+1}:</b>", heading_style))
        story.append(Paragraph(f"{query['query']}", normal_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # Split the response into explanation, context, and references
        response_text = query['response']
        explanation_match = re.search(r'### Explanation\n(.*?)\n###', response_text, re.DOTALL)
        context_match = re.search(r'### Additional Context\n(.*?)\n###', response_text, re.DOTALL)
        references_match = re.search(r'### References\n(.*)', response_text, re.DOTALL)
        
        explanation = explanation_match.group(1).strip() if explanation_match else ""
        context = context_match.group(1).strip() if context_match else ""
        references_str = references_match.group(1).strip() if references_match else ""
        
        story.append(Paragraph(f"<b>Explanation:</b>", heading_style))
        story.append(Paragraph(f"{explanation.replace('_', '')}", normal_style))
        story.append(Spacer(1, 0.2 * inch))
        
        if context:
            story.append(Paragraph(f"<b>Additional Context:</b>", heading_style))
            story.append(Paragraph(f"{context.replace('_', '')}", normal_style))
            story.append(Spacer(1, 0.2 * inch))
        
        if references_str:
            story.append(Paragraph(f"<b>References:</b>", heading_style))
            for ref in references_str.split('\n'):
                # Remove the number and space from the beginning of the reference
                parts = ref.split(' - ', 1)
                if len(parts) > 1:
                    source, url = parts[0], parts[1]
                    # Make the links clickable
                    story.append(Paragraph(f"{source} - <a href=\"{url}\" color=\"blue\">{url}</a>", reference_style))
                else:
                    story.append(Paragraph(ref, reference_style))
            story.append(Spacer(1, 0.2 * inch))
        
        story.append(Spacer(1, 0.5 * inch))

    doc.build(story)
