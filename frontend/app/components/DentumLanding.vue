<script setup lang="ts">
const { locale, setLocale } = useI18n()

const isRussian = computed(() => locale.value.toLowerCase().startsWith('ru'))

const copy = computed(() => isRussian.value
  ? {
      description: 'Рабочее пространство стоматологической клиники: пациенты, расписание, одонтограмма и планы лечения в Dentum.',
      skip: 'Перейти к содержимому',
      navStory: 'Возможности',
      navWorkflow: 'Как устроено',
      signIn: 'Войти',
      language: 'Переключить язык на английский',
      eyebrow: 'РАБОЧЕЕ ПРОСТРАНСТВО СТОМАТОЛОГИИ',
      heroTitle: 'Стоматология,\nсобранная в одном месте.',
      heroBody: 'Пациенты, расписание, одонтограмма и планы лечения — в едином рабочем пространстве клиники.',
      enter: 'Открыть Dentum',
      scroll: 'Прокрутите, чтобы увидеть Dentum в работе',
      chapters: [
        {
          eyebrow: '01 / КЛИНИЧЕСКАЯ КАРТА',
          title: 'Клиническая картина — ясная.',
          body: 'Одонтограмма, записи приёма и история пациента связаны в одной карте. Нужные детали остаются рядом с лечением.',
          cardLabel: 'ОДОНТОГРАММА',
          cardTitle: 'Зуб 26',
          cardBody: 'Карта пациента',
          cardMark: '26'
        },
        {
          eyebrow: '02 / ПЛАН ЛЕЧЕНИЯ',
          title: 'Следующий шаг виден заранее.',
          body: 'Соберите этапы лечения в последовательный план и возвращайтесь к нему из карты пациента.',
          cardLabel: 'ПЛАН ЛЕЧЕНИЯ',
          cardTitle: 'Этапы лечения',
          cardBody: 'План · приём · наблюдение',
          cardMark: '→'
        },
        {
          eyebrow: '03 / РАСПИСАНИЕ КЛИНИКИ',
          title: 'День клиники складывается в ритм.',
          body: 'Расписание приёмов помогает команде видеть рабочий день и держать пациентов в поле внимания.',
          cardLabel: 'РАСПИСАНИЕ',
          cardTitle: 'Рабочий день',
          cardBody: 'Приёмы · пациенты · команда',
          cardMark: '✓'
        },
        {
          eyebrow: 'DENTUM / РАБОЧЕЕ ПРОСТРАНСТВО',
          title: 'Меньше разрозненных экранов. Больше ясности в работе.',
          body: 'Начните с Dentum и соберите повседневную работу клиники в понятный процесс.',
          cardLabel: 'DENTUM',
          cardTitle: 'Общая картина клиники',
          cardBody: 'Пациенты · лечение · расписание',
          cardMark: '✳'
        }
      ],
      openApp: 'Войти в Dentum',
      manual: 'Руководство',
      footer: 'Рабочее пространство для стоматологических клиник.'
    }
  : {
      description: 'A workspace for dental clinics: patients, scheduling, odontograms and treatment plans in Dentum.',
      skip: 'Skip to content',
      navStory: 'Capabilities',
      navWorkflow: 'How it works',
      signIn: 'Sign in',
      language: 'Switch language to Russian',
      eyebrow: 'THE DENTAL CLINIC WORKSPACE',
      heroTitle: 'Dentistry,\nin one clear workspace.',
      heroBody: 'Patients, scheduling, odontograms and treatment plans come together in one workspace for your clinic.',
      enter: 'Explore Dentum',
      scroll: 'Scroll to see Dentum in motion',
      chapters: [
        {
          eyebrow: '01 / CLINICAL RECORD',
          title: 'A clearer clinical picture.',
          body: 'Odontograms, visit notes and patient history stay connected in one record, with useful details close to care.',
          cardLabel: 'ODONTOGRAM',
          cardTitle: 'Tooth 26',
          cardBody: 'Patient record',
          cardMark: '26'
        },
        {
          eyebrow: '02 / TREATMENT PLAN',
          title: 'See the next step ahead.',
          body: 'Arrange treatment into a clear sequence and return to it from the patient record.',
          cardLabel: 'TREATMENT PLAN',
          cardTitle: 'Care sequence',
          cardBody: 'Plan · visit · follow-up',
          cardMark: '→'
        },
        {
          eyebrow: '03 / CLINIC SCHEDULE',
          title: 'Bring the clinic day into rhythm.',
          body: 'A shared appointments schedule helps the team see the day and keep patients in view.',
          cardLabel: 'SCHEDULE',
          cardTitle: 'Clinic day',
          cardBody: 'Appointments · patients · team',
          cardMark: '✓'
        },
        {
          eyebrow: 'DENTUM / THE CLINIC WORKSPACE',
          title: 'Fewer disconnected screens. More clarity at work.',
          body: 'Start with Dentum and bring everyday clinic work into a clear, connected process.',
          cardLabel: 'DENTUM',
          cardTitle: 'One view of your clinic',
          cardBody: 'Patients · care · schedule',
          cardMark: '✳'
        }
      ],
      openApp: 'Sign in to Dentum',
      manual: 'User manual',
      footer: 'A workspace for dental clinics.'
    })

const chapters = computed(() => copy.value.chapters)
const pageTitle = computed(() => isRussian.value ? 'Dentum — система для стоматологической клиники' : 'Dentum — a workspace for dental clinics')
useSeoMeta({
  title: pageTitle,
  description: computed(() => copy.value.description),
  ogTitle: pageTitle,
  ogDescription: computed(() => copy.value.description),
  ogType: 'website'
})

async function toggleLocale() {
  await setLocale(isRussian.value ? 'en' : 'ru')
}
</script>

<template>
  <main
    id="top"
    class="dentum-landing"
  >
    <a
      class="landing-skip"
      href="#story"
    >{{ copy.skip }}</a>

    <header class="landing-header">
      <a
        class="landing-brand"
        href="#top"
        :aria-label="isRussian ? 'Dentum — главная' : 'Dentum — home'"
      >
        <span
          class="landing-brand__symbol"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 32 32"
            fill="none"
          >
            <path
              d="M8.1 5.7c2.6-1.1 5.1.8 7.9.8s5.3-1.9 7.9-.8c3.2 1.3 3.5 5.4 2.2 9.1-1.1 3.1-2.9 5.7-3.6 9.1-.4 1.8-1.2 3.2-2.5 3.2-1.5 0-1.9-2.7-2.6-4.5-.4-1.1-.8-1.6-1.4-1.6s-1 .5-1.4 1.6c-.7 1.8-1.1 4.5-2.6 4.5-1.3 0-2.1-1.4-2.5-3.2-.7-3.4-2.5-6-3.6-9.1C4.6 11.1 4.9 7 8.1 5.7Z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span class="landing-brand__word">Dentum</span>
      </a>

      <nav
        class="landing-nav"
        :aria-label="isRussian ? 'Основная навигация' : 'Main navigation'"
      >
        <a href="#capabilities">{{ copy.navStory }}</a>
        <a href="#workflow">{{ copy.navWorkflow }}</a>
      </nav>

      <div class="landing-header__actions">
        <button
          class="landing-language"
          type="button"
          :aria-label="copy.language"
          @click="toggleLocale"
        >
          {{ isRussian ? 'EN' : 'RU' }}
        </button>
        <a
          class="landing-sign-in"
          href="/login"
        >{{ copy.signIn }} <span aria-hidden="true">↗</span></a>
      </div>
    </header>

    <DentumScrollScene
      id="story"
      :chapters="chapters"
      :scroll-label="copy.scroll"
    >
      <section
        class="story-chapter story-chapter--hero"
        aria-labelledby="landing-hero-title"
      >
        <div class="story-copy story-copy--hero">
          <p class="story-eyebrow">
            <span class="story-eyebrow__dot" />{{ copy.eyebrow }}
          </p>
          <h1
            id="landing-hero-title"
            class="story-title story-title--hero"
          >
            {{ copy.heroTitle }}
          </h1>
          <p class="story-body story-body--hero">
            {{ copy.heroBody }}
          </p>
          <div class="story-actions">
            <a
              class="landing-primary"
              href="/login"
            >{{ copy.enter }} <span aria-hidden="true">↗</span></a>
            <a
              class="landing-secondary"
              href="#capabilities"
            >
              <span
                class="landing-secondary__icon"
                aria-hidden="true"
              >↓</span>{{ copy.navStory }}
            </a>
          </div>
          <div class="story-model-credit">
            <a
              href="https://sketchfab.com/3d-models/maxillary-first-molar-e719a474ef7e4bd7abec508f85f1e984"
              target="_blank"
              rel="noopener noreferrer"
            >{{ isRussian ? 'Maxillary First Molar · University of Dundee · Sketchfab' : 'Maxillary First Molar · University of Dundee · Sketchfab' }}</a>
            <span>·</span>
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
            >CC BY 4.0</a>
            <span>· {{ isRussian ? 'сетка и материал изменены' : 'mesh and material modified' }}</span>
          </div>
          <div class="story-caption">
            <span class="story-caption__line" />
            <span>{{ isRussian ? 'Клинические данные · единый рабочий процесс' : 'Clinical records · one connected workflow' }}</span>
          </div>
        </div>
        <span
          class="story-index"
          aria-hidden="true"
        >01 <i /> 05</span>
      </section>

      <section
        v-for="(chapter, index) in chapters"
        :id="index === 0 ? 'capabilities' : index === 1 ? 'workflow' : index === chapters.length - 1 ? 'landing-cta' : `chapter-${index + 1}`"
        :key="chapter.eyebrow"
        class="story-chapter"
        :class="{ 'story-chapter--final': index === chapters.length - 1 }"
        :aria-labelledby="`chapter-title-${index}`"
      >
        <div class="story-copy">
          <p class="story-eyebrow">
            <span class="story-eyebrow__number">0{{ index + 1 }}</span>{{ chapter.eyebrow }}
          </p>
          <h2
            :id="`chapter-title-${index}`"
            class="story-title"
          >
            {{ chapter.title }}
          </h2>
          <p class="story-body">
            {{ chapter.body }}
          </p>
          <div
            v-if="index === chapters.length - 1"
            class="story-actions story-actions--final"
          >
            <a
              class="landing-primary"
              href="/login"
            >{{ copy.openApp }} <span aria-hidden="true">↗</span></a>
            <a
              class="landing-secondary"
              href="https://dentum.online/docs/user-manual/en/"
            >{{ copy.manual }} <span aria-hidden="true">↗</span></a>
          </div>
          <a
            v-else
            class="story-next"
            :href="index === 0 ? '#workflow' : index === chapters.length - 2 ? '#landing-cta' : `#chapter-${index + 2}`"
          >
            <span>{{ isRussian ? 'Продолжить' : 'Continue' }}</span><span aria-hidden="true">↓</span>
          </a>
        </div>
        <span
          class="story-index"
          aria-hidden="true"
        >0{{ index + 2 }} <i /> 05</span>
      </section>
    </DentumScrollScene>

    <footer class="landing-footer">
      <a
        class="landing-brand landing-brand--footer"
        href="#top"
        :aria-label="isRussian ? 'Dentum — вверх страницы' : 'Dentum — back to top'"
      >
        <span
          class="landing-brand__symbol"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 32 32"
            fill="none"
          ><path
            d="M8.1 5.7c2.6-1.1 5.1.8 7.9.8s5.3-1.9 7.9-.8c3.2 1.3 3.5 5.4 2.2 9.1-1.1 3.1-2.9 5.7-3.6 9.1-.4 1.8-1.2 3.2-2.5 3.2-1.5 0-1.9-2.7-2.6-4.5-.4-1.1-.8-1.6-1.4-1.6s-1 .5-1.4 1.6c-.7 1.8-1.1 4.5-2.6 4.5-1.3 0-2.1-1.4-2.5-3.2-.7-3.4-2.5-6-3.6-9.1C4.6 11.1 4.9 7 8.1 5.7Z"
            fill="currentColor"
          /></svg>
        </span>
        <span class="landing-brand__word">Dentum</span>
      </a>
      <p>{{ copy.footer }}</p>
      <a
        class="landing-footer__manual"
        href="https://dentum.online/docs/user-manual/en/"
      >{{ copy.manual }} <span aria-hidden="true">↗</span></a>
      <span class="landing-footer__copyright">© {{ new Date().getFullYear() }} Dentum</span>
    </footer>
  </main>
</template>

<style scoped>
.dentum-landing {
  --landing-ink: #153039;
  --landing-ink-soft: #36545b;
  --landing-muted: #627980;
  --landing-teal: #087f8c;
  --landing-blue: #31a9ca;
  --landing-paper: #f4f6f3;
  --landing-edge: rgba(21, 48, 57, .13);
  min-height: 100vh;
  overflow: clip;
  background: var(--landing-paper);
  color: var(--landing-ink);
  font-family: 'Inter Variable', Inter, sans-serif;
}

.landing-skip {
  position: fixed;
  z-index: 30;
  top: 8px;
  left: 8px;
  padding: 10px 14px;
  transform: translateY(-160%);
  border-radius: 6px;
  background: #fff;
  color: var(--landing-ink);
  box-shadow: 0 5px 20px #15303924;
}

.landing-skip:focus { transform: translateY(0); }

.landing-header {
  position: fixed;
  z-index: 20;
  inset: 0 0 auto;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 78px;
  padding: 0 clamp(22px, 5vw, 78px);
  border-bottom: 1px solid rgba(21, 48, 57, .09);
  background: rgba(244, 246, 243, .84);
  backdrop-filter: blur(18px);
}

.landing-brand { display: inline-flex; width: fit-content; align-items: center; gap: 10px; text-decoration: none; color: inherit; }
.landing-brand__symbol { display: grid; width: 30px; height: 30px; place-items: center; color: var(--landing-teal); }
.landing-brand__symbol svg { width: 26px; height: 26px; }
.landing-brand__word { font-size: 18px; font-weight: 700; letter-spacing: -.045em; }

.landing-nav { display: flex; align-items: center; gap: clamp(22px, 3vw, 46px); }
.landing-nav a, .landing-language, .landing-sign-in { font: inherit; font-size: 12px; font-weight: 600; letter-spacing: .01em; text-decoration: none; color: var(--landing-ink-soft); }
.landing-nav a { transition: color .18s ease; }
.landing-nav a:hover, .landing-footer__manual:hover { color: var(--landing-teal); }
.landing-header__actions { display: flex; align-items: center; justify-content: flex-end; gap: 22px; }
.landing-language { padding: 8px 3px; border: 0; background: transparent; cursor: pointer; }
.landing-sign-in { display: inline-flex; align-items: center; gap: 14px; padding: 11px 16px; border: 1px solid var(--landing-edge); border-radius: 5px; transition: border-color .2s, background .2s, color .2s; }
.landing-sign-in:hover { border-color: var(--landing-ink); background: var(--landing-ink); color: white; }

.dentum-story { position: relative; isolation: isolate; }
.story-chapter {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(330px, 40vw) minmax(0, 1fr);
  min-height: 100svh;
  align-items: center;
  padding: 94px clamp(30px, 8vw, 128px) 54px clamp(30px, 8vw, 128px);
  scroll-margin-top: 78px;
}

.story-copy { grid-column: 1; width: min(100%, 570px); padding: 22px 0; }
.story-copy--hero { padding-top: 64px; }
.story-eyebrow { display: flex; align-items: center; gap: 12px; margin: 0 0 26px; color: var(--landing-teal); font-size: 10px; font-weight: 700; letter-spacing: .14em; line-height: 1.6; }
.story-eyebrow__dot { width: 7px; height: 7px; border-radius: 50%; background: var(--landing-teal); box-shadow: 0 0 0 5px rgba(8, 127, 140, .09); }
.story-eyebrow__number { display: inline-grid; min-width: 26px; height: 22px; place-items: center; border: 1px solid rgba(8, 127, 140, .24); border-radius: 2px; font-size: 9px; letter-spacing: .04em; }
.story-title { max-width: 590px; margin: 0; font-size: clamp(42px, 5.2vw, 76px); font-weight: 570; letter-spacing: -.071em; line-height: .99; text-wrap: balance; }
.story-title--hero { max-width: 680px; font-size: clamp(50px, 6.8vw, 96px); white-space: pre-line; }
.story-body { max-width: 430px; margin: 24px 0 0; color: var(--landing-muted); font-size: clamp(14px, 1.15vw, 16px); line-height: 1.75; text-wrap: pretty; }
.story-body--hero { max-width: 470px; margin-top: 26px; }
.story-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin-top: 32px; }
.landing-primary { display: inline-flex; min-height: 48px; align-items: center; justify-content: center; gap: 28px; padding: 0 18px; border: 1px solid var(--landing-ink); border-radius: 4px; background: var(--landing-ink); color: #fff; font-size: 12px; font-weight: 650; text-decoration: none; transition: transform .18s ease, background .18s ease; }
.landing-primary:hover { transform: translateY(-2px); background: var(--landing-teal); }
.landing-primary span, .landing-sign-in span { font-size: 15px; line-height: 1; }
.landing-secondary { display: inline-flex; align-items: center; gap: 9px; min-height: 42px; padding: 0 4px; color: var(--landing-ink-soft); font-size: 12px; font-weight: 600; text-decoration: none; }
.landing-secondary:hover { color: var(--landing-teal); }
.landing-secondary__icon { display: grid; width: 23px; height: 23px; place-items: center; border: 1px solid var(--landing-edge); border-radius: 50%; font-size: 13px; }
.story-caption { display: flex; align-items: center; gap: 12px; margin-top: 62px; color: #849499; font-size: 9px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; }
.story-caption__line { width: 28px; height: 1px; background: #91afb3; }
.story-model-credit { display: none; }
.story-next { display: inline-flex; align-items: center; gap: 16px; margin-top: 30px; color: var(--landing-ink-soft); font-size: 11px; font-weight: 650; text-decoration: none; }
.story-next span:last-child { display: grid; width: 26px; height: 26px; place-items: center; border: 1px solid var(--landing-edge); border-radius: 50%; transition: transform .2s; }
.story-next:hover span:last-child { transform: translateY(3px); }
.story-index { position: absolute; right: clamp(30px, 5vw, 80px); bottom: 42px; display: flex; align-items: center; gap: 12px; color: #91a0a2; font-size: 9px; font-variant-numeric: tabular-nums; letter-spacing: .08em; }
.story-index i { display: block; width: 45px; height: 1px; background: #bac6c4; }
.story-chapter--final .story-title { max-width: 550px; font-size: clamp(42px, 5vw, 72px); }

.landing-footer { position: relative; z-index: 2; display: flex; min-height: 106px; align-items: center; gap: 28px; padding: 20px clamp(22px, 5vw, 78px); border-top: 1px solid var(--landing-edge); background: var(--landing-paper); }
.landing-brand--footer .landing-brand__symbol { width: 24px; height: 24px; }
.landing-brand--footer .landing-brand__symbol svg { width: 22px; height: 22px; }
.landing-brand--footer .landing-brand__word { font-size: 15px; }
.landing-footer p { margin: 0 auto 0 0; color: var(--landing-muted); font-size: 11px; }
.landing-footer__manual { color: var(--landing-ink-soft); font-size: 11px; font-weight: 600; text-decoration: none; }
.landing-footer__copyright { color: #87989b; font-size: 10px; font-variant-numeric: tabular-nums; }

.dentum-landing a:focus-visible, .dentum-landing button:focus-visible { outline: 3px solid #31a9ca; outline-offset: 4px; }

@media (min-width: 1200px) {
  .story-chapter { grid-template-columns: minmax(420px, 42vw) minmax(0, 1fr); }
  .story-copy { width: min(100%, 600px); }
}

@media (max-width: 760px) {
  .landing-header { min-height: 66px; grid-template-columns: 1fr auto; padding: 0 18px; }
  .landing-brand__symbol { width: 25px; height: 25px; }
  .landing-brand__symbol svg { width: 23px; height: 23px; }
  .landing-brand__word { font-size: 16px; }
  .landing-nav { display: none; }
  .landing-header__actions { gap: 13px; }
  .landing-sign-in { gap: 8px; padding: 9px 11px; font-size: 11px; }
  .landing-language { font-size: 11px; }
  .story-chapter { display: flex; min-height: 100svh; align-items: flex-end; padding: 0 18px max(9svh, 48px); scroll-margin-top: 66px; }
  .story-copy, .story-copy--hero { width: 100%; max-width: none; padding: 20px 19px 22px; border: 1px solid rgba(21, 48, 57, .08); border-radius: 10px; background: rgba(250, 251, 249, .94); box-shadow: 0 16px 48px rgba(21, 48, 57, .07); backdrop-filter: blur(14px); }
  .story-eyebrow { gap: 9px; margin-bottom: 15px; font-size: 9px; letter-spacing: .11em; }
  .story-title, .story-title--hero, .story-chapter--final .story-title { max-width: 560px; font-size: clamp(34px, 9vw, 50px); letter-spacing: -.065em; line-height: 1.02; }
  .story-body, .story-body--hero { max-width: 540px; margin-top: 14px; font-size: 13px; line-height: 1.6; }
  .story-actions { gap: 10px; margin-top: 19px; }
  .story-model-credit { display: flex; flex-wrap: wrap; align-items: center; gap: 3px; margin-top: 10px; color: #87989b; font-size: 7px; line-height: 1.4; }
  .story-model-credit a { color: inherit; text-decoration: underline; text-decoration-color: rgba(135, 152, 155, .45); text-underline-offset: 2px; }
  .landing-primary { min-height: 43px; gap: 16px; padding: 0 13px; font-size: 11px; }
  .landing-secondary { font-size: 11px; }
  .story-caption, .story-next { display: none; }
  .story-index { right: 21px; bottom: 18px; z-index: 3; gap: 8px; font-size: 8px; }
  .story-index i { width: 26px; }
  .landing-footer { flex-wrap: wrap; gap: 16px; padding: 22px 19px; }
  .landing-footer p { order: 3; flex-basis: 100%; font-size: 10px; }
  .landing-footer__manual { margin-left: auto; font-size: 10px; }
  .landing-footer__copyright { font-size: 9px; }
}

@media (prefers-reduced-motion: reduce) {
  .landing-sign-in, .landing-primary, .story-next span:last-child, .landing-nav a { transition: none; }
}
</style>
