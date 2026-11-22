// The Rust component library: the shared components every page builds from.
// Each entry needs a stories file under rust/stories/<category path>/ (the
// category lower-cased, spaces as hyphens: 'Components/Data display' ->
// components/data-display/) whose `component` is that file and whose title
// starts with the category (testing/rust/library.test.ts enforces it).
// Feature-specific blocks (fleet boards, campaign tables, ...) stay out.
//
// Tiers (rust/docs/Architecture.mdx): Foundations (tokens, type, icons; pages
// generated from src/styles, not listed here) -> Layout (composition
// primitives) -> Components (by purpose) -> EVE (domain components, SDE) ->
// Page (page chrome).
export const RUST_LIBRARY = {
    'Layout': [
        'compositions/Wrapper', 'compositions/Grid', 'compositions/FlexInline', 'compositions/FlexInlineSiblings',
        'compositions/Flexblock', 'compositions/FixedFluid', 'compositions/FluidFixed', 'compositions/BlockList',
        'compositions/XFadeScroll', 'compositions/Cover', 'compositions/Center',
    ],
    'Components/Forms': [
        'blocks/Button', 'blocks/StylessButton', 'blocks/ButtonStack', 'blocks/ButtonConfirm', 'blocks/ClipboardButton',
        'blocks/Input', 'blocks/InputError', 'blocks/Select', 'blocks/Textarea', 'blocks/StylessTextArea',
        'blocks/RadioCheckInput', 'blocks/UnstyledRadioCheckButton', 'blocks/Switch', 'blocks/SwitchSquare',
        'blocks/FlatPicker', 'blocks/Kbd', 'blocks/Combobox',
    ],
    'Components/Feedback': [
        'blocks/EmptyState', 'blocks/ErrorRefetch', 'blocks/ShowAlert', 'blocks/Progress', 'blocks/PageProgress',
        'blocks/Countdown', 'blocks/LocalTime', 'blocks/CountUpAnimation', 'blocks/StatusText', 'blocks/LazyPartial',
        'blocks/SkipToContent',
    ],
    'Components/Data display': [
        'blocks/Badge', 'blocks/Tag', 'blocks/TextBadge', 'blocks/NotificationBadge', 'blocks/VisibilityTag',
        'blocks/DebugTag', 'blocks/ComponentBlock', 'blocks/ComponentBlockHeader', 'blocks/CollapsibleBlock',
        'blocks/CollapsableButton', 'blocks/StatCard', 'blocks/RowList', 'blocks/DataGrid', 'blocks/DataTable', 'blocks/Chart', 'blocks/Carousel', 'blocks/TextGroup',
        'blocks/Square', 'blocks/Markdown', 'blocks/Marquee', 'blocks/SettingRow', 'blocks/NumberNameTooltip',
        'blocks/Tile', 'blocks/OptionCard', 'blocks/Card', 'blocks/PictureCard',
    ],
    'Components/Navigation': [
        'blocks/ActionMenu', 'blocks/ActionMenuItem', 'blocks/Dropdown', 'blocks/SectionTabs', 'blocks/SectionTabPanel',
        'blocks/HtmxPager', 'blocks/FilterChip', 'blocks/ChipGroup', 'blocks/Breadcrumb', 'blocks/ExternalLink',
    ],
    'Components/Overlays': [
        'blocks/Dialog', 'blocks/DialogBase', 'blocks/DialogButton', 'blocks/AlertDialog', 'blocks/ConfirmDialog', 'blocks/Modal', 'blocks/Tippy',
    ],
    'EVE': [
        'blocks/Picture', 'blocks/CharacterPicture', 'blocks/CorporationPicture', 'blocks/ItemPicture',
        'blocks/CorporationBadge', 'blocks/AllianceBadge', 'blocks/PilotBadge', 'blocks/ItemBadge',
        'blocks/CharacterCard', 'blocks/TimezoneTags',
        // SDE: static data shown and searched (src/helpers/sde/, rust/fixtures/sde.json)
        'blocks/sde/SecurityStatus', 'blocks/sde/MetaGroupTag', 'blocks/sde/ShipSlots', 'blocks/sde/SolarSystemTag',
        'blocks/sde/TypeRow', 'blocks/sde/TypeResults', 'blocks/sde/SolarSystemResults', 'blocks/sde/TypeSearch',
        'blocks/sde/SolarSystemSearch',
    ],
    'Page': [
        'page/PageTitle', 'page/PageSubheader', 'page/PageActions', 'page/PageBreadcrumbs', 'page/BreadcrumbLink',
        'layout/TextBox', 'layout/Context',
    ],
} as const

export type RustCategory = keyof typeof RUST_LIBRARY

// Icons and logos are Foundations: gallery stories render every file in
// src/components/icons/ and src/components/logos/ (rust/components/*Gallery.astro).
