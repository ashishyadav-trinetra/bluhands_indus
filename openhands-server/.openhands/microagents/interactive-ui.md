---
name: interactive-ui
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- search
- filter
- sort
- modal
- dialog
- dropdown
- menu
- toggle
- tab
- accordion
- pagination
- form
- input
- select
- checkbox
- radio
- switch
- slider
- toast
- notification
- popover
- tooltip
- table
- data table
- list
- sidebar
- drawer
- sheet
- click
- interactive
- dynamic
- state
- todo
- task
- dashboard
- admin
- panel
- settings
- CRUD
---

# Interactive UI — EVERY Interactive Element MUST Work

## THE #1 RULE: If it looks clickable, it MUST do something.

Every button, link, input, dropdown, tab, and toggle MUST have a working event handler
with visible state change. A search bar that doesn't filter is BROKEN. A filter button
that doesn't open a menu is BROKEN. A modal trigger that doesn't open a modal is BROKEN.

## MANDATORY: Use shadcn/ui for ALL interactive elements

```bash
# Install the components you need BEFORE building
npx shadcn@latest add button input dialog dropdown-menu select tabs sheet \
  accordion popover tooltip table badge command switch checkbox radio-group \
  separator scroll-area toast
```

NEVER build custom dropdowns, modals, or menus from scratch. shadcn/ui handles
accessibility, keyboard navigation, animations, and edge cases that DIY components miss.

## Search Bar (MUST filter in real-time)

```tsx
import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

function SearchableList({ items }: { items: Item[] }) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(
    () => items.filter(item =>
      item.name.toLowerCase().includes(query.toLowerCase()) ||
      item.description?.toLowerCase().includes(query.toLowerCase())
    ),
    [items, query]
  );

  return (
    <div>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </div>
      <div className="mt-4 space-y-2">
        {filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No results found for "{query}"
          </p>
        ) : (
          filtered.map(item => <ItemCard key={item.id} item={item} />)
        )}
      </div>
    </div>
  );
}
```

**NEVER** render an `<Input>` without `onChange` + state + filtering logic.

## Filter/Sort Controls (MUST change the displayed data)

```tsx
import { useState, useMemo } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

type SortKey = 'name' | 'date' | 'price';
type FilterStatus = 'all' | 'active' | 'archived';

function FilterableTable({ data }: { data: Item[] }) {
  const [sortBy, setSortBy] = useState<SortKey>('date');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');

  const processed = useMemo(() => {
    let result = [...data];
    // Filter
    if (filterStatus !== 'all') {
      result = result.filter(item => item.status === filterStatus);
    }
    // Sort
    result.sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'date') return new Date(b.date).getTime() - new Date(a.date).getTime();
      if (sortBy === 'price') return b.price - a.price;
      return 0;
    });
    return result;
  }, [data, sortBy, filterStatus]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as FilterStatus)}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="archived">Archived</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortKey)}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date">Newest first</SelectItem>
            <SelectItem value="name">Name A-Z</SelectItem>
            <SelectItem value="price">Price high-low</SelectItem>
          </SelectContent>
        </Select>

        <span className="text-sm text-muted-foreground ml-auto">
          {processed.length} result{processed.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Render the processed data */}
    </div>
  );
}
```

## Modals/Dialogs (MUST open and close properly)

```tsx
import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

function DeleteConfirmDialog({ onDelete }: { onDelete: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">Delete</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Are you sure?</DialogTitle>
          <DialogDescription>This action cannot be undone.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="destructive" onClick={() => { onDelete(); setOpen(false); }}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

## Tabs (MUST switch content)

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="analytics">Analytics</TabsTrigger>
    <TabsTrigger value="settings">Settings</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">...</TabsContent>
  <TabsContent value="analytics">...</TabsContent>
  <TabsContent value="settings">...</TabsContent>
</Tabs>
```

## Data Tables with Actions (MUST have working row actions)

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { MoreHorizontal, Pencil, Trash } from 'lucide-react';

function DataTable({ rows, onEdit, onDelete }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-[50px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(row => (
          <TableRow key={row.id}>
            <TableCell>{row.name}</TableCell>
            <TableCell><Badge variant={row.active ? 'default' : 'secondary'}>{row.status}</Badge></TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onEdit(row.id)}>
                    <Pencil className="mr-2 h-4 w-4" /> Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onDelete(row.id)} className="text-destructive">
                    <Trash className="mr-2 h-4 w-4" /> Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

## State Management Rules

1. **Every input** MUST have `value` + `onChange` (controlled component)
2. **Every list** that can be searched/filtered MUST use `useMemo` for derived data
3. **Every form** MUST track submission state: `const [isSubmitting, setIsSubmitting] = useState(false)`
4. **Every async action** MUST show loading state and handle errors
5. **Every delete** MUST show a confirmation dialog first
6. **Every empty state** MUST show a helpful message, not a blank page

## TESTING CHECKLIST (MANDATORY before calling Finish)

After building any interactive UI, you MUST test each interactive element:

1. **Click every button** — does it do something visible?
2. **Type in every input** — does the UI respond (filter, validate, update)?
3. **Open every dropdown/dialog** — does it open AND close properly?
4. **Submit every form** — does it show loading state, then success/error?
5. **Check empty states** — what happens with no data? Does it show a message?
6. **Check error states** — what happens if the API fails? Does it show an error?

If ANY interactive element is non-functional, FIX IT before proceeding.

## Anti-Patterns (NEVER DO THESE)

- ❌ `<input>` without `onChange` or `value`
- ❌ `<button onClick={() => {}}>` or `<button>` with no handler
- ❌ Building a custom dropdown with `div` + `position: absolute` (use shadcn DropdownMenu)
- ❌ Building a custom modal with `div` + `z-index` (use shadcn Dialog)
- ❌ `console.log` as the only action in an onClick handler
- ❌ Search input that doesn't filter anything
- ❌ Filter buttons that are purely decorative
- ❌ Table with no row actions or empty action menus
- ❌ Form with no validation feedback
- ❌ Loading states that never resolve
