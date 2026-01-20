import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State, callback, ALL
import base64
import io
import os

app = dash.Dash(__name__)

default_csv = "/Users/random/Library/Mobile Documents/com~apple~CloudDocs/Desktop/aha_list_release phases_260116223046.csv"
default_df = pd.DataFrame()  # Load lazily when needed

def process_scheduler_data(df, end_date=None):
    """Process and aggregate scheduler data"""
    df['Schedule phase start'] = pd.to_datetime(df['Schedule phase start'])
    df['Schedule phase end'] = pd.to_datetime(df['Schedule phase end'])
    df = df[df['Schedule name'] != 'Company Holidays'].copy()
    july_2025 = pd.to_datetime('2025-07-01')
    df = df[df['Schedule phase end'] >= july_2025].copy()
    
    # Filter by end date if provided
    if end_date:
        end_date_dt = pd.to_datetime(end_date) if isinstance(end_date, str) else end_date
        df = df[df['Schedule phase start'] <= end_date_dt].copy()
    
    # For FTO & Workload schedules, treat each phase as separate bar
    fto_workload = df[df['Schedule name'].str.contains('FTO & Workload', na=False)].copy()
    other_schedules = df[~df['Schedule name'].str.contains('FTO & Workload', na=False)].copy()
    
    # FTO & Workload: group by phase name, start, end (each phase is own bar)
    if not fto_workload.empty:
        fto_scheduler = fto_workload[['Goal name', 'Schedule phase name', 'Schedule phase start', 'Schedule phase end']].copy()
        fto_scheduler.rename(columns={
            'Schedule phase name': 'Schedule',
            'Schedule phase start': 'Start Date',
            'Schedule phase end': 'End Date',
            'Goal name': 'Goal'
        }, inplace=True)
        fto_scheduler['Is_FTO_Workload'] = True
        fto_scheduler = fto_scheduler.drop_duplicates()
    else:
        fto_scheduler = pd.DataFrame()
    
    # Other schedules: group by Goal + Schedule name
    if not other_schedules.empty:
        other_scheduler = other_schedules.groupby(['Goal name', 'Schedule name']).agg({
            'Schedule phase start': 'min',
            'Schedule phase end': 'max'
        }).reset_index()
        other_scheduler.rename(columns={
            'Schedule phase start': 'Start Date',
            'Schedule phase end': 'End Date',
            'Goal name': 'Goal',
            'Schedule name': 'Schedule'
        }, inplace=True)
        other_scheduler['Is_FTO_Workload'] = False
    else:
        other_scheduler = pd.DataFrame()
    
    # Combine both
    scheduler_df = pd.concat([fto_scheduler, other_scheduler], ignore_index=True)
    
    scheduler_df['Duration Days'] = (scheduler_df['End Date'] - scheduler_df['Start Date']).dt.days
    scheduler_df = scheduler_df.sort_values(['Goal', 'Start Date'])
    
    return scheduler_df

def process_tickets_data(df):
    """Process tickets and extract assignee initials"""
    if df.empty:
        return pd.DataFrame()
    
    df['Due date'] = pd.to_datetime(df['Due date'])
    
    # Handle Requested - make it optional, defaulting to Due date if missing
    if 'Requested' in df.columns:
        df['Requested'] = pd.to_datetime(df['Requested'])
    else:
        df['Requested'] = df['Due date']  # Default to due date if no Requested column
    
    # Extract initials from assignee names (First + Last)
    def get_initials(name):
        if pd.isna(name) or name == '':
            return ''
        parts = str(name).split()
        if len(parts) >= 2:
            return parts[0][0].upper() + parts[-1][0].upper()
        return parts[0][0].upper() if len(parts) > 0 else ''
    
    df['Assignee Initials'] = df['Assignee'].apply(get_initials)
    df = df[df['Assignee Initials'] != ''].copy()  # Filter out empty initials
    
    # Rename for consistency
    df.rename(columns={
        'Due date': 'DueDate',
        'Requested': 'RequestedDate',
        'Subject': 'Title',
        'Status': 'TicketStatus'
    }, inplace=True)
    
    return df[['Assignee', 'Assignee Initials', 'ID', 'Title', 'RequestedDate', 'DueDate', 'TicketStatus']]

def create_gantt_chart(scheduler_df, expanded_goals=None, visible_goals=None, end_date=None, tickets_df=None):
    """Create Gantt chart with expand/collapse and goal visibility filtering"""
    
    if expanded_goals is None:
        expanded_goals = {}
    if visible_goals is None:
        visible_goals = set(scheduler_df['Goal'].unique())
    if tickets_df is None:
        tickets_df = pd.DataFrame()
    
    unique_goals = sorted(scheduler_df['Goal'].unique())
    colors_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                      '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                      '#aec7e8', '#ffbb78']
    colors_map = {goal: colors_palette[i % len(colors_palette)] for i, goal in enumerate(unique_goals)}
    
    fig = go.Figure()
    tasks = []
    task_data = []
    header_positions = {}
    y_pos = 0
    
    # Build hierarchical task list
    for goal in unique_goals:
        goal_display = goal.replace('I-', '')
        is_expanded = expanded_goals.get(goal, True)
        
        expand_indicator = "▼" if is_expanded else "▶"
        goal_label = f"{expand_indicator} {goal_display}"
        tasks.append(goal_label)
        task_data.append(('header', goal))
        header_positions[goal] = y_pos
        y_pos += 1
        
        if is_expanded:
            goal_schedules = scheduler_df[scheduler_df['Goal'] == goal].copy()
            # Sort: FTO schedules first, then by start date
            goal_schedules['is_fto'] = goal_schedules['Schedule'].str.contains('FTO', case=False, na=False).astype(int)
            goal_schedules = goal_schedules.sort_values(['is_fto', 'Start Date'], ascending=[False, True])
            
            for idx, row in goal_schedules.iterrows():
                schedule_label = f"  → {row['Schedule']}"
                tasks.append(schedule_label)
                task_data.append((row['Start Date'], row['End Date'], row['Duration Days'], goal, row['Schedule']))
                y_pos += 1
            
            # Add tickets for this goal (match by initials)
            goal_initials = goal.replace('I-', '')  # e.g., 'AN' from 'I-AN'
            goal_tickets = tickets_df[tickets_df['Assignee Initials'] == goal_initials].copy() if not tickets_df.empty else pd.DataFrame()
            if not goal_tickets.empty:
                for idx, row in goal_tickets.iterrows():
                    ticket_label = f"    🎫 #{row['ID']} {row['Title'][:30]}"
                    tasks.append(ticket_label)
                    task_data.append((row['RequestedDate'], row['DueDate'], 0, goal, row['TicketStatus'], 'ticket', row['Title']))
                    y_pos += 1
    
    # Create shapes and hover traces for schedule bars
    shapes = []
    # Ticket status colors
    ticket_colors = {'Open': '#27ae60', 'Pending': '#f39c12', 'On-hold': '#e74c3c'}
    
    for idx, task in enumerate(tasks):
        if isinstance(task_data[idx], tuple) and task_data[idx][0] != 'header':
            task_tuple = task_data[idx]
            start_date = task_tuple[0]
            end_date = task_tuple[1]
            duration = task_tuple[2]
            goal = task_tuple[3]
            
            # Check if it's a ticket (has more than 5 elements and 6th element is 'ticket')
            is_ticket = len(task_tuple) > 5 and task_tuple[5] == 'ticket'
            ticket_status = task_tuple[4]
            ticket_subject = task_tuple[6] if is_ticket and len(task_tuple) > 6 else ''
            
            # Only show if goal is visible
            if goal in visible_goals:
                goal_display = goal.replace('I-', '')
                
                if is_ticket:
                    # Ticket: use status color, small height, marker style
                    color = ticket_colors.get(ticket_status, '#95a5a6')
                    height = 0.25
                else:
                    # Schedule: use goal color, normal height
                    schedule = task_tuple[4]
                    color = colors_map[goal]
                    height = 0.15
                
                shapes.append(dict(
                    type='rect',
                    x0=start_date,
                    x1=end_date,  # Use end_date directly for tickets now (DueDate)
                    y0=idx - height,
                    y1=idx + height,
                    fillcolor=color,
                    opacity=0.7 if is_ticket else 0.8,
                    line=dict(color=color, width=2 if is_ticket else 1)
                ))
                
                # Hover trace with enhanced ticket info
                mid_date = start_date + (end_date - start_date) / 2
                
                if is_ticket:
                    hover_text = f"<b>{ticket_subject}</b><br>Ticket #{task_tuple[1]}<br>Status: {ticket_status}<br>Requested: {start_date.strftime('%Y-%m-%d')}<br>Due: {end_date.strftime('%Y-%m-%d')}<extra></extra>"
                else:
                    schedule = task_tuple[4]
                    hover_text = (
                        f"<b>{goal_display}</b><br>"
                        f"{schedule}<br>"
                        f"{start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}<br>"
                        f"Duration: {duration} days<extra></extra>"
                    )
                
                fig.add_trace(go.Scatter(
                    x=[mid_date],
                    y=[idx],
                    mode='markers',
                    marker=dict(size=0),
                    hovertemplate=hover_text,
                    showlegend=False,
                    hoverinfo='text'
                ))
    
    # Add clickable header bars - larger and easier to click
    x_min = scheduler_df['Start Date'].min()
    x_max = scheduler_df['End Date'].max()
    x_range = x_max - x_min
    
    # Add invisible wide Scatter traces at header positions for easier clicking
    for goal in unique_goals:
        goal_display = goal.replace('I-', '')
        y_idx = header_positions[goal]
        
        # Add large invisible clickable area at the start of timeline
        fig.add_trace(go.Scatter(
            x=[x_min],
            y=[y_idx],
            mode='markers',
            marker=dict(size=50, color='rgba(0,0,0,0)', line=dict(width=0)),
            customdata=[[goal]],
            hovertemplate=f"<b>{goal_display} — Click to expand/collapse</b><extra></extra>",
            showlegend=False,
            hoverinfo='text'
        ))
        
        # Also add visible light blue bar for visual feedback
        fig.add_trace(go.Bar(
            x=[x_range * 0.15],
            y=[y_idx],
            base=x_min,
            orientation='h',
            marker=dict(color='rgba(100, 150, 200, 0.12)', line=dict(color='rgba(100, 150, 200, 0.25)', width=1)),
            customdata=[[goal]],
            hovertemplate=f"<b>{goal_display} — Click to expand/collapse</b><extra></extra>",
            showlegend=False,
            hoverinfo='text',
            width=0.4
        ))
    
    # Legend removed - use goal toggle buttons instead
    
    # Legend removed - use goal toggle buttons instead
    
    # Update layout
    fig.update_layout(
        shapes=shapes,
        title='Release Scheduler — Timeline by Goal & Schedule (From July 2025)',
        xaxis_title='Timeline',
        yaxis_title='',
        height=max(600, len(tasks) * 20),
        margin=dict(l=350, r=150, t=100, b=50),
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='white',
        font=dict(size=11),
        hovermode='closest',
        yaxis=dict(
            tickvals=list(range(len(tasks))),
            ticktext=tasks,
            autorange='reversed'
        ),
        xaxis=dict(
            type='date',
            tickformat='%Y-%m-%d',
            side='bottom',
            showgrid=True,
            gridwidth=1,
            gridcolor='#e0e0e0'
        ),
        showlegend=False
    )
    
    return fig

def get_next_openings(scheduler_df):
    """Get the three people with earliest available openings based on last non-FTO schedule + 2 days, 
    avoiding long PTO periods"""
    if scheduler_df.empty:
        return html.Div("No schedules loaded yet.", style={'textAlign': 'center', 'color': '#7f8c8d'})
    
    # Exclude FTO & Workload schedules completely from planning
    working_schedules = scheduler_df[scheduler_df['Is_FTO_Workload'] == False].copy()
    
    if working_schedules.empty:
        return html.Div("No eligible schedules found.", style={'textAlign': 'center', 'color': '#7f8c8d'})
    
    # Separate remaining PTO/FTO from other schedules
    pto_schedules = working_schedules[working_schedules['Schedule'].str.contains('FTO', na=False)].copy()
    non_pto_schedules = working_schedules[~working_schedules['Schedule'].str.contains('FTO', na=False)].copy()
    
    # Get latest end date for each goal from NON-PTO schedules only
    goal_last_dates = non_pto_schedules.groupby('Goal')['End Date'].max()
    
    # Calculate openings: 2 days after last non-PTO schedule
    adjusted_openings = {}
    for goal, last_date in goal_last_dates.items():
        opening_date = last_date + pd.Timedelta(days=2)
        
        # Check if opening date falls within any PTO period
        if not pto_schedules.empty:
            goal_pto = pto_schedules[pto_schedules['Goal'] == goal].copy()
            
            for _, pto_row in goal_pto.iterrows():
                pto_start = pto_row['Start Date']
                pto_end = pto_row['End Date']
                pto_duration = (pto_end - pto_start).days
                
                # If opening falls within PTO and PTO is > 3 days, push past it
                if opening_date >= pto_start and opening_date <= pto_end:
                    if pto_duration > 3:
                        opening_date = pto_end + pd.Timedelta(days=1)
        
        adjusted_openings[goal] = opening_date
    
    # Convert to Series and sort
    goal_openings_series = pd.Series(adjusted_openings)
    goal_openings_series = goal_openings_series.sort_values()
    
    # Filter out excluded ones
    excluded = {'AR', 'SD', 'RR', 'BW'}
    filtered_openings = goal_openings_series[[g.replace('I-', '') not in excluded for g in goal_openings_series.index]]
    
    if len(filtered_openings) == 0:
        return html.Div("No eligible schedules found.", style={'textAlign': 'center', 'color': '#7f8c8d'})
    
    # Get top 3 from eligible people
    top_3 = filtered_openings.head(3)
    
    if len(top_3) == 0:
        return html.Div("No eligible openings found.", style={'textAlign': 'center', 'color': '#7f8c8d'})
    
    items = []
    for i, (goal, opening_date) in enumerate(top_3.items(), 1):
        goal_display = goal.replace('I-', '')
        opening_str = opening_date.strftime('%b %d, %Y')
        items.append(
            html.Div([
                html.Span(f"{i}. ", style={'fontWeight': 'bold', 'color': '#2c3e50'}),
                html.Span(goal_display, style={'fontWeight': 'bold', 'color': '#2980b9'}),
                html.Span(f" — Available: ", style={'color': '#7f8c8d'}),
                html.Span(opening_str, style={'fontWeight': 'bold', 'color': '#27ae60'})
            ], style={'marginBottom': 8, 'fontSize': 15})
        )
    
    return html.Div(items, style={'padding': 10})

app.layout = html.Div([
    html.H1("Release Scheduler — Interactive Timeline", style={'textAlign': 'center', 'marginBottom': 10}),
    html.P("Organized by Goal and Schedule (Company Holidays Excluded)", 
           style={'textAlign': 'center', 'color': '#7f8c8d', 'marginBottom': 30}),
    
    dcc.Store(id='scheduler-data-store'),
    dcc.Store(id='tickets-data-store'),
    dcc.Store(id='expanded-goals-store', data={}),
    dcc.Store(id='visible-goals-store', data={}),
    dcc.Store(id='end-date-store', data='2027-01-31'),
    
    html.Div([
        html.H3('🚀 Next Openings', style={'marginBottom': 15, 'color': '#2c3e50'}),
        html.Div(id='next-openings-display', style={
            'backgroundColor': '#ecf0f1',
            'border': '2px solid #3498db',
            'borderRadius': 5,
            'padding': 15,
            'marginBottom': 20
        })
    ], style={'padding': 15, 'backgroundColor': '#ffffff'}),
    
    html.Div([
        html.Div([
            html.H4('AHA Release Phases', style={'marginBottom': 10}),
            dcc.Upload(
                id='upload-aha-data',
                children=html.Div([
                    '📤 Drag and drop or ',
                    html.A('select an AHA export CSV file')
                ]),
                style={
                    'width': '95%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '2px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px auto',
                    'backgroundColor': '#ecf0f1',
                    'cursor': 'pointer',
                    'fontSize': 14
                },
                multiple=False
            ),
            html.Div(id='upload-status', style={'marginTop': 10, 'textAlign': 'center', 'fontWeight': 'bold'})
        ], style={'width': '48%', 'display': 'inline-block', 'marginRight': '2%', 'verticalAlign': 'top'}),
        html.Div([
            html.H4('Zendesk Tickets', style={'marginBottom': 10}),
            dcc.Upload(
                id='upload-tickets-data',
                children=html.Div([
                    '📋 Drag and drop or ',
                    html.A('select a Zendesk tickets CSV file')
                ]),
                style={
                    'width': '95%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '2px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px auto',
                    'backgroundColor': '#ecf0f1',
                    'cursor': 'pointer',
                    'fontSize': 14
                },
                multiple=False
            ),
            html.Div(id='tickets-upload-status', style={'marginTop': 10, 'textAlign': 'center', 'fontWeight': 'bold'})
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'})
    ], style={'padding': 15, 'backgroundColor': '#f8f9fa', 'borderRadius': 5}),
    
    html.Div([
        html.Div([
            html.Label('Filter by Goal:', style={'fontWeight': 'bold', 'marginRight': 10}),
            dcc.Dropdown(
                id='goal-filter-dropdown',
                options=[],
                value='All',
                style={'display': 'inline-block', 'width': '300px'}
            )
        ], style={'marginBottom': 15}),
        html.Div([
            html.Label('Expand/Collapse Goals:', style={'fontWeight': 'bold', 'marginRight': 10}),
            html.Button('Expand All', id='expand-all-btn', n_clicks=0, style={'marginRight': 10, 'padding': '5px 10px'}),
            html.Button('Collapse All', id='collapse-all-btn', n_clicks=0, style={'padding': '5px 10px'})
        ], style={'marginBottom': 15}),

        html.Div([
            html.Label('Timeline End Date:', style={'fontWeight': 'bold', 'marginRight': 10}),
            dcc.Slider(
                id='end-date-slider',
                min=0,
                max=10,
                value=10,
                marks={
                    0: 'Jul 2025', 1: 'Aug', 2: 'Sep', 3: 'Oct', 4: 'Nov', 5: 'Dec',
                    6: 'Jan 2026', 7: 'Feb', 8: 'Mar', 9: 'Apr', 10: 'May 2026'
                },
                tooltip={"placement": "bottom", "always_visible": True},
                step=1,
                included=False
            ),
            html.Div(id='end-date-display', style={'marginTop': 10, 'fontSize': 12, 'color': '#555'})
        ], style={})
    ], style={'padding': 15, 'backgroundColor': '#f8f9fa', 'borderRadius': 5}),
    
    html.Div(id='goal-toggle-buttons', style={'padding': 10, 'marginBottom': 15, 'backgroundColor': '#f0f0f0', 'borderRadius': 5}),
    
    html.Div([
        html.Div(id='scheduler-stats', style={'padding': 15, 'backgroundColor': '#ecf0f1', 'borderRadius': 5})
    ], style={'marginBottom': 20}),
    
    dcc.Graph(id='gantt-chart', style={'marginTop': 20})
    
], style={'padding': 25, 'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#ffffff'})

@callback(
    Output('next-openings-display', 'children'),
    Input('scheduler-data-store', 'data'),
    prevent_initial_call=False
)
def update_next_openings(stored_data):
    """Update the next openings display when scheduler data is loaded"""
    if not stored_data:
        return html.Div("Upload AHA schedules to see next openings.", style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': 14})
    
    try:
        df = pd.read_json(stored_data, orient='split')
        scheduler_df = process_scheduler_data(df, end_date=None)
        return get_next_openings(scheduler_df)
    except Exception as e:
        return html.Div(f"Error: {str(e)}", style={'textAlign': 'center', 'color': '#e74c3c'})

@callback(
    [Output('tickets-data-store', 'data'),
     Output('tickets-upload-status', 'children')],
    Input('upload-tickets-data', 'contents'),
    State('upload-tickets-data', 'filename'),
    prevent_initial_call=True
)
def update_tickets_data(contents, filename):
    if contents is None:
        raise dash.exceptions.PreventUpdate
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        df_new = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        
        required_cols = ['Assignee', 'Due date', 'Subject', 'Status', 'ID', 'Requested']
        optional_cols = []
        if not all(col in df_new.columns for col in required_cols):
            return None, f'❌ Error: Missing required columns. Need: {required_cols}'
        # Note: Requested column is required (Requested = Start date, Due date = End date)
        
        json_data = df_new.to_json(date_format='iso', orient='split')
        status_msg = f'✓ Loaded {len(df_new)} tickets from {filename}'
        return json_data, status_msg
    
    except Exception as e:
        return None, f'❌ Error: {str(e)}'

@callback(
    [Output('scheduler-data-store', 'data'),
     Output('upload-status', 'children'),
     Output('goal-filter-dropdown', 'options')],
    Input('upload-aha-data', 'contents'),
    State('upload-aha-data', 'filename'),
    prevent_initial_call=True
)
def update_scheduler_data(contents, filename):
    if contents is None:
        raise dash.exceptions.PreventUpdate
    
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        df_new = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        
        required_cols = ['Goal name', 'Schedule name', 'Schedule phase start', 'Schedule phase end']
        if not all(col in df_new.columns for col in required_cols):
            return None, f'❌ Error: Missing required columns', []
        
        json_data = df_new.to_json(date_format='iso', orient='split')
        status_msg = f'✓ Loaded {len(df_new)} records from {filename}'
        
        goals = sorted(df_new['Goal name'].unique())
        goal_options = [{'label': 'All Goals', 'value': 'All'}] + [{'label': g.replace('I-', ''), 'value': g} for g in goals]
        
        return json_data, status_msg, goal_options
    
    except Exception as e:
        return None, f'❌ Error: {str(e)}', []

@callback(
    Output('goal-filter-dropdown', 'options', allow_duplicate=True),
    Input('scheduler-data-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def init_goal_filter(stored_data):
    """Initialize filter dropdown on page load"""
    if stored_data:
        df = pd.read_json(stored_data, orient='split')
    elif not default_df.empty:
        df = default_df.copy()
    else:
        return []
    
    goals = sorted(df['Goal name'].unique())
    return [{'label': 'All Goals', 'value': 'All'}] + [{'label': g.replace('I-', ''), 'value': g} for g in goals]

@callback(
    [Output('end-date-store', 'data'),
     Output('end-date-display', 'children')],
    Input('end-date-slider', 'value'),
    prevent_initial_call=False
)
def update_end_date(slider_value):
    """Convert slider value to date"""
    dates = [
        '2025-07-31', '2025-08-31', '2025-09-30', '2025-10-31', '2025-11-30', '2025-12-31',
        '2026-01-31', '2026-02-28', '2026-03-31', '2026-04-30', '2026-05-31'
    ]
    end_date = dates[slider_value] if slider_value < len(dates) else '2026-05-31'
    display = f"Viewing through {pd.to_datetime(end_date).strftime('%B %Y')}"
    return end_date, display

@callback(
    Output('visible-goals-store', 'data', allow_duplicate=True),
    Input('scheduler-data-store', 'data'),
    prevent_initial_call='initial_duplicate'
)

def init_visible_goals(stored_data):
    """Initialize visible goals to all goals when data loads"""
    if stored_data:
        df = pd.read_json(stored_data, orient='split')
    elif not default_df.empty:
        df = default_df.copy()
    else:
        return {}
    
    all_goals = sorted(df['Goal name'].unique())
    return {g: True for g in all_goals}

@callback(
    [Output('gantt-chart', 'figure'),
     Output('scheduler-stats', 'children'),
     Output('goal-toggle-buttons', 'children')],
    [Input('scheduler-data-store', 'data'),
     Input('goal-filter-dropdown', 'value'),
     Input('visible-goals-store', 'data'),
     Input('expanded-goals-store', 'data'),
     Input('end-date-store', 'data'),
     Input('tickets-data-store', 'data')],
    prevent_initial_call=False
)
def update_chart(stored_data, selected_goal, visible_goals, expanded_goals, end_date, tickets_data):
    try:
        if stored_data:
            df = pd.read_json(stored_data, orient='split')
        elif not default_df.empty:
            df = default_df.copy()
        else:
            return go.Figure().add_annotation(text='No data'), html.Div(), html.Div()
        
        scheduler_df = process_scheduler_data(df, end_date=end_date or '2027-01-31')
        
        # Process tickets
        tickets_df = pd.DataFrame()
        if tickets_data:
            tickets_df_raw = pd.read_json(tickets_data, orient='split')
            tickets_df = process_tickets_data(tickets_df_raw)
        
        if selected_goal and selected_goal != 'All':
            scheduler_df = scheduler_df[scheduler_df['Goal'] == selected_goal]
        
        if scheduler_df.empty:
            return go.Figure().add_annotation(text='No data'), html.Div(), html.Div()
        
        # Convert visible_goals dict to set for filtering in chart
        if isinstance(visible_goals, dict):
            visible_goals_set = set([g for g, v in visible_goals.items() if v])
        else:
            visible_goals_set = set(scheduler_df['Goal'].unique())
        
        if not visible_goals_set:
            visible_goals_set = set(scheduler_df['Goal'].unique())
        
        fig = create_gantt_chart(scheduler_df, expanded_goals or {}, visible_goals_set, end_date or '2026-05-31', tickets_df)
        
        total_schedules = len(scheduler_df)
        total_goals = len(scheduler_df['Goal'].unique())
        earliest_start = scheduler_df['Start Date'].min().strftime('%Y-%m-%d')
        latest_end = scheduler_df['End Date'].max().strftime('%Y-%m-%d')
        overall_duration = (scheduler_df['End Date'].max() - scheduler_df['Start Date'].min()).days
        avg_duration = scheduler_df['Duration Days'].mean()
        
        stats = html.Div([
            html.Span(f"📊 Schedules: {total_schedules}  |  "),
            html.Span(f"🎯 Goals: {total_goals}  |  "),
            html.Span(f"📅 {earliest_start} → {latest_end}  |  "),
            html.Span(f"⏱️ {overall_duration} days overall  |  "),
            html.Span(f"📈 Avg: {avg_duration:.0f} days"),
        ], style={'fontSize': 13, 'color': '#2c3e50'})
        
        unique_goals = sorted(scheduler_df['Goal'].unique())
        toggle_buttons = []
        for goal in unique_goals:
            is_expanded = expanded_goals.get(goal, True) if expanded_goals else True
            label = f"{'▼' if is_expanded else '▶'} {goal.replace('I-', '')}"
            toggle_buttons.append(
                html.Button(
                    label,
                    id={'type': 'goal-toggle-btn', 'index': goal},
                    n_clicks=0,
                    style={
                        'marginRight': 8,
                        'marginBottom': 8,
                        'padding': '8px 12px',
                        'backgroundColor': '#e8f4f8',
                        'border': '1px solid #5DADE2',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'fontWeight': 'bold'
                    }
                )
            )
        
        return fig, stats, html.Div(toggle_buttons, style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '8px'})
    
    except Exception as e:
        import traceback
        print(f"ERROR in update_chart: {e}")
        print(traceback.format_exc())
        return go.Figure().add_annotation(text=f'Error: {str(e)}'), html.Div(f'Error: {e}'), html.Div()

@callback(
    Output('visible-goals-store', 'data', allow_duplicate=True),
    Input('gantt-chart', 'clickData'),
    State('visible-goals-store', 'data'),
    State('scheduler-data-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def handle_legend_click(click_data, visible_goals, stored_data):
    """Handle legend clicks: toggle goal visibility"""
    # For now, just pass through - legend clicking is complex in Plotly
    # Users can use the goal toggle buttons instead
    raise dash.exceptions.PreventUpdate

@callback(
    Output('expanded-goals-store', 'data', allow_duplicate=True),
    Input({'type': 'goal-toggle-btn', 'index': ALL}, 'n_clicks'),
    State('expanded-goals-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def toggle_btn(n_clicks, expanded_goals):
    if not n_clicks or sum(n_clicks) == 0:
        raise dash.exceptions.PreventUpdate
    
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    goal = eval(button_id)['index']
    
    expanded_goals = expanded_goals or {}
    expanded_goals[goal] = not expanded_goals.get(goal, True)
    return expanded_goals

@callback(
    Output('expanded-goals-store', 'data', allow_duplicate=True),
    Input('expand-all-btn', 'n_clicks'),
    State('scheduler-data-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def expand_all(n_clicks, stored_data):
    if n_clicks == 0:
        raise dash.exceptions.PreventUpdate
    
    df = pd.read_json(stored_data, orient='split') if stored_data else default_df.copy()
    return {g: True for g in sorted(df['Goal name'].unique())}

@callback(
    Output('expanded-goals-store', 'data', allow_duplicate=True),
    Input('collapse-all-btn', 'n_clicks'),
    State('scheduler-data-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def collapse_all(n_clicks, stored_data):
    if n_clicks == 0:
        raise dash.exceptions.PreventUpdate
    
    df = pd.read_json(stored_data, orient='split') if stored_data else default_df.copy()
    return {g: False for g in sorted(df['Goal name'].unique())}

if __name__ == '__main__':
    app.run_server(debug=False, host='127.0.0.1', port=8052)

# Expose Flask server for gunicorn
server = app.server


# Auto-collapse goals not in top 3 next openings on data load
@callback(
    Output('expanded-goals-store', 'data', allow_duplicate=True),
    Input('next-openings-goals-store', 'data'),
    prevent_initial_call='initial_duplicate'
)
def auto_collapse_non_top_openings(next_openings_goals):
    """Collapse all goals except those in top 3 next openings"""
    if not next_openings_goals:
        raise dash.exceptions.PreventUpdate
    
    # Create expanded state: True only for next openings goals
    expanded_state = {goal: True for goal in next_openings_goals}
    return expanded_state
