# Whipping Cog for RedBot

A Discord bot cog designed to manage direct messaging campaigns for the Libcord Update Command (UC), preventing Discord throttling through pre-established DM connections.

## Overview

This cog solves the problem of Discord throttling during mass DM campaigns by:
- Pre-establishing DM connections between UC members and server members ("zen mode")
- Using RAID-like striping to distribute members across multiple UC members for redundancy
- Tracking which users have been messaged to avoid duplicates
- Providing organized lists for systematic messaging during updates

## How It Works

### RAID-like Striping System

Each Libcord member is assigned to multiple UC members (default: 3) using a striping algorithm similar to RAID arrays. This ensures:
- Redundancy: If one UC member is unavailable, others can cover their assigned users
- Load balancing: Work is distributed evenly across all UC members
- Efficiency: Minimizes the chance of having to create new DM conversations during critical updates

### Two Operating Modes

1. **Zen Mode**: Pre-emptive messaging to establish DM connections
   - Run during quiet periods before major operations
   - Sends a friendly message to establish the DM channel
   - Tracks progress to avoid re-messaging

2. **Whipping Mode**: Active messaging during liberation updates
   - Provides lists of users to message about the current update
   - Automatically excludes users with the "Updating" role
   - Can target online-only users or everyone
   - Tracks which users have been messaged for the current update

## Setup

### Required Roles
The cog looks for these Discord roles:
- `Update Command` - Main UC role
- `Junior Command` - Alternative UC role
- `Liberator` - General member role (optional)
- `Updating` - Active update indicator role (optional)

### Initial Configuration

1. **Set up user assignments** (Bot Owner only):
   ```
   [p]whip setup [stripe_count]
   ```
   - `stripe_count`: Number of UC members each user is assigned to (default: 3)
   - This distributes all current server members among UC members

2. **Configure message templates** (Bot Owner only):
   ```
   [p]whip templates zen "Your zen mode message here"
   [p]whip templates whip "Your whipping mode message here"
   ```

## Commands

All commands require the `Update Command` or `Junior Command` role unless specified.

### Basic Commands

- `[p]whip` - Show help for whip commands
- `[p]whip mystats` - View your assignment statistics and progress
- `[p]whip assignments [@user]` - View assignments (yours or a specific UC member's)

### Zen Mode (Pre-emptive Messaging)

- `[p]whip zen [limit]` - Get list of unmessaged users with standard template
- `[p]whip zensilent [limit]` - Get list with @silent prefix template (minimizes disruption)
- `[p]whip progress @user` - Mark a user as messaged in zen mode

### Whipping Mode (Active Updates)

- `[p]whip whipmode [online_only]` - Start whipping mode for an update
  - `online_only`: True (default) = only online users, False = all users
  - Users with the "Updating" role are automatically excluded
- `[p]whip done @user` - Mark a user as messaged during current update
- `[p]whip report` - View statistics for the current update

### Admin Commands (Bot Owner Only)

- `[p]whip setup [stripe_count]` - Initialize or reconfigure assignments
- `[p]whip templates [zen|whip] [new_template]` - View or update message templates
- `[p]whip reassign @user @from_uc @to_uc` - Reassign a user between UC members

## Usage Examples

### Before a Major Update (Zen Mode)

1. UC members run zen mode to establish connections:
   ```
   [p]whip zen 20
   ```
   This shows 20 users to message with the zen template.

2. After messaging users, mark them as complete:
   ```
   [p]whip progress @User1
   [p]whip progress @User2
   ```

3. Check your progress:
   ```
   [p]whip mystats
   ```

### During an Update (Whipping Mode)

1. Start whipping mode:
   ```
   [p]whip whipmode
   ```
   This shows online users to message (excluding those with the "Updating" role).

2. As you message users, mark them done:
   ```
   [p]whip done @User1
   [p]whip done @User2
   ```

3. View update progress:
   ```
   [p]whip report
   ```

## Features

- **Automatic Assignment**: New members joining the server are automatically assigned to UC members
- **Progress Tracking**: Separate tracking for zen mode (permanent) and whipping mode (per-update)
- **Flexible Templates**: Customizable message templates for different scenarios
- **Silent Mode**: Option to use @silent prefix to minimize notification disruption
- **Statistics**: Track your messaging progress and view reports for each update
- **Redundancy**: Multiple UC members assigned to each user prevents single points of failure

## Best Practices

1. **Regular Zen Sessions**: Run zen mode regularly to maintain DM connections with new members
2. **Update Templates**: Keep templates concise and informative
3. **Mark Progress**: Always mark users as messaged to maintain accurate tracking
4. **Check Stats**: Review your stats before updates to ensure good coverage
5. **Use Silent Mode**: Consider using zensilent for non-urgent connection establishment

## Troubleshooting

- **"You don't have any assigned users!"**: Contact a bot owner to run `[p]whip setup`
- **Missing users in lists**: They may have left the server or been reassigned
- **Can't mark progress**: Ensure you're marking users assigned to you
- **No Update Command role found**: Ensure the role exists with exact name "Update Command"

## Data Storage

The cog stores:
- User assignments (which UC members are responsible for which users)
- Zen progress (permanent record of established DM connections)
- Update progress (per-update record of who was messaged)
- Message templates
- Configuration settings (stripe count)

All data is stored per-guild using RedBot's Config system.