import asyncio
from itertools import batched, chain
from typing import Generator, List, Tuple, cast

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag
from eliot import start_action

from .vars import headers


def clean_tree(title: str, id: int, body: str) -> BeautifulSoup:
    original_soup = BeautifulSoup(body)
    new_soup = BeautifulSoup(
        """
    <h1 class="chapter-name" id={id}>{title}</h1>
    <section class="chapter-body"></section>
"""
    )

    insert_at = cast(Tag, new_soup.find("section"))

    children = cast(Tag, original_soup.find("body")).children
    for tag in cast(list[Tag], list(children)):
        if tag.name != "p":  # Casted to lower
            print(tag.name)
            continue

        style = tag.attrs.get("style")
        for child in cast(list[Tag], tag.children):
            # tag is a <p> enclosing either text, media, or a break

            if child.name in [None, "b", "i", "u"]:
                # text is enclosed, can be italic, bold, underlined, or a mix
                tag.attrs = {}
                p_tag = tag
                if style:
                    p_tag["style"] = style
                insert_at.append(p_tag)
                break

            elif child.name == "img":
                # image is enclosed
                img_tag = Tag(name="img")
                img_tag.attrs = {
                    "height": child.attrs.get("data-original-height"),
                    "width": child.attrs.get("data-original-width"),
                    "src": child["src"],
                }
                if style:
                    img_tag["style"] = style
                insert_at.append(img_tag)

            elif child.name == "br":
                # br tag is enclosed
                br_tag = Tag(name="br", can_be_empty_element=True)
                if style:
                    br_tag["style"] = style
                insert_at.append(br_tag)

    return new_soup


async def fetch_image(url: str) -> bytes | None:
    """Fetch image bytes."""
    with start_action(action_type="api_fetch_image", url=url):
        async with ClientSession(headers=headers) as session:  # Don't cache images.
            async with session.get(url) as response:
                if not response.ok:
                    return None

                body = await response.read()

        return body


async def download_tree_images(tree: BeautifulSoup) -> Generator[bytes]:
    """Return a Generator of bytes containing image data for all images referenced in the tree."""
    image_urls = [img["src"] for img in tree.find_all("img")]
    downloaded_images: Generator[bytes] = chain(
        await asyncio.gather(*[fetch_image(url) for url in chunk])
        for chunk in batched(image_urls, 3)
    )
    return downloaded_images
