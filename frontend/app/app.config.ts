export default defineAppConfig({
  ui: {
    colors: {
      primary: 'denplant',
      neutral: 'stone',
      success: 'green',
      info: 'sky',
      warning: 'amber',
      error: 'red'
    },
    button: {
      slots: {
        base: 'font-heading'
      },
      defaultVariants: {
        size: 'sm',
        color: 'neutral',
        variant: 'soft'
      }
    },
    badge: {
      defaultVariants: {
        variant: 'subtle',
        size: 'sm'
      }
    },
    card: {
      slots: {
        root: 'bg-[var(--color-surface)] ring-1 ring-[var(--color-border)] shadow-[var(--shadow-card)] rounded-[var(--radius-xl)]',
        header: 'px-4 py-3 sm:px-5 sm:py-4 border-b border-[var(--color-border-subtle)]',
        body: 'p-4 sm:p-5',
        footer: 'px-4 py-3 sm:px-5 sm:py-4 border-t border-[var(--color-border-subtle)]'
      }
    },
    modal: {
      slots: {
        overlay: 'bg-[rgba(15,17,22,0.40)] dark:bg-[rgba(0,0,0,0.55)]',
        content: 'bg-[var(--color-surface)] ring-1 ring-[var(--color-border)] shadow-[var(--shadow-lg)] rounded-[var(--radius-xl)]'
      }
    },
    tabs: {
      slots: {
        list: 'bg-[var(--color-surface-muted)] !rounded-[var(--radius-md)] !p-0.5',
        indicator: '!bg-[var(--color-surface)] !shadow-[var(--shadow-xs)] !rounded-[calc(var(--radius-md)-2px)]',
        trigger: 'data-[state=active]:!text-default'
      },
      compoundVariants: [
        {
          color: 'primary',
          variant: 'pill',
          class: {
            indicator: 'bg-[var(--color-surface)]',
            trigger: 'data-[state=active]:text-default focus-visible:outline-[var(--color-primary)]'
          }
        },
        {
          color: 'neutral',
          variant: 'pill',
          class: {
            indicator: 'bg-[var(--color-surface)]',
            trigger: 'data-[state=active]:text-default focus-visible:outline-[var(--color-primary)]'
          }
        }
      ]
    }
  }
})
