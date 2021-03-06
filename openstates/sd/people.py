import re

from pupa.scrape import Person, Scraper, Organization

import lxml.html


class SDLegislatorScraper(Scraper):

    def scrape(self, chambers=None):
        self._committees = {}

        url = 'http://www.sdlegislature.gov/Legislators/default.aspx'
        if chambers is None:
            chambers = ['upper', 'lower']
        for chamber in chambers:
            if chamber == 'upper':
                search = 'Senate Legislators'
            else:
                search = 'House Legislators'

            page = self.get(url).text
            page = lxml.html.fromstring(page)
            page.make_links_absolute(url)

            # Legisltor listing has initially-hidden <div>s that
            # contain the members for just a particular chamber
            for link in page.xpath(
                "//h4[text()='{}']".format(search) +
                "/../span/section/table/tbody/tr/td/a"
            ):
                name = link.text.strip()
                yield from self.scrape_legislator(name, chamber, link.attrib['href'])
        yield from self._committees.values()

    def scrape_legislator(self, name, chamber, url):
        page = self.get(url).text
        page = lxml.html.fromstring(page)
        page.make_links_absolute(url)

        party = page.xpath("string(//span[contains(@id, 'Party')])")
        party = party.strip()

        if party == 'Democrat':
            party = 'Democratic'

        district = page.xpath("string(//span[contains(@id, 'District')])")
        district = district.strip().lstrip('0')

        occupation = page.xpath(
            "string(//span[contains(@id, 'Occupation')])")
        occupation = occupation.strip()

        (photo_url, ) = page.xpath('//img[contains(@id, "_imgMember")]/@src')

        office_phone = page.xpath(
            "string(//span[contains(@id, 'CapitolPhone')])").strip()

        email = None

        email_link = page.xpath('//a[@id="lnkMail"]')

        legislator = Person(primary_org=chamber,
                            image=photo_url,
                            name=name,
                            party=party,
                            district=district
                            )
        legislator.extras['occupation'] = occupation
        if office_phone.strip() != "":
            legislator.add_contact_detail(type='voice', value=office_phone, note='Capitol Office')
        if email_link:
            email = email_link[0].attrib['href'].split(":")[1]
            legislator.add_contact_detail(type='email', value=email, note='Capitol Office')

        # SD is hiding their email addresses entirely in JS now, so
        # search through <script> blocks looking for them
        for script in page.xpath('//script'):
            if script.text:
                match = re.search(r'([\w.]+@sdlegislature\.gov)', script.text)
                if match:
                    legislator.add_contact_detail(type='email',
                                                  value=match.group(0),
                                                  note='Capitol Office')
                    break

        home_address = [
                x.strip() for x in
                page.xpath('//td/span[contains(@id, "HomeAddress")]/text()')
                if x.strip()
                ]
        if home_address:
            home_address = "\n".join(home_address)
            home_phone = page.xpath(
                "string(//span[contains(@id, 'HomePhone')])").strip()
            legislator.add_contact_detail(type='address',
                                          value=home_address,
                                          note='District Office')
            if home_phone:
                legislator.add_contact_detail(type='voice',
                                              value=home_phone,
                                              note='District Office')

        legislator.add_source(url)
        legislator.add_link(url)

        committees = page.xpath('//div[@id="divCommittees"]/span/section/table/tbody/tr/td/a')
        for committee in committees:
            self.scrape_committee(legislator, url, committee, chamber)
        yield legislator

    def scrape_committee(self, leg, url, element, chamber):
        comm = element.text.strip()
        if comm.startswith('Joint '):
            chamber = 'legislature'

        role = element.xpath('../following-sibling::td')[0].text_content().lower().strip()

        org = self.get_organization(comm, chamber)
        org.add_source(url)
        leg.add_membership(org, role=role)

    def get_organization(self, name, chamber):
        key = (name, chamber)
        if key not in self._committees:
            self._committees[key] = Organization(name=name,
                                                 chamber=chamber,
                                                 classification='committee')
        return self._committees[key]
