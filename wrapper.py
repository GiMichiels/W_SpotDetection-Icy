import logging
import os
import sys
from argparse import ArgumentParser
from subprocess import call

import numpy as np
from cytomine import CytomineJob
from cytomine.models import Annotation, AnnotationTerm, Job, ImageInstanceCollection, Property
from shapely.ops import cascaded_union
from shapely.affinity import affine_transform
from skimage import io
from sldc import locator

def add_annotation(img_inst, polygon, label=None, proba=1.0):
    image_id = img_inst.id
    # Transform in cartesian coordinates
    polygon = affine_transform(polygon, [1, 0, 0, -1, 0, img_inst.height])

    annotation = Annotation(polygon.wkt, image_id).save()
    if label is not None and annotation is not None:
        annotation_term = AnnotationTerm()
        annotation_term.annotation = annotation.id
        annotation_term.annotationIdent = annotation.id
        annotation_term.userannotation = annotation.id
        annotation_term.term = label
        annotation_term.expectedTerm = label
        annotation_term.rate = proba
        annotation_term.save()
    return annotation

def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


parser = ArgumentParser(prog="Icy-SpotDetection.py", description="Icy workflow to detect spots in 2D images")
parser.add_argument('--cytomine_host', dest="cytomine_host", default='http://localhost-core')
parser.add_argument('--cytomine_public_key', dest="cytomine_public_key", default="")
parser.add_argument('--cytomine_private_key', dest="cytomine_private_key", default="")
parser.add_argument("--cytomine_id_project", dest="cytomine_id_project", default="5378")
parser.add_argument("--icy_scale3sensitivity", dest="scale3sens", default="40")
params, others = parser.parse_known_args(sys.argv)

base_path = "/icy/data"

with CytomineJob(params.cytomine_host, params.cytomine_public_key, params.cytomine_private_key, params.cytomine_id_software, params.cytomine_id_project, verbose=logging.INFO) as cj:
    cj.job.update(status=Job.RUNNING, progress=0, statusComment="Initialisation...")

    working_path = os.path.join(base_path, str(cj.job.id))
    in_path = os.path.join(working_path, "in")
    makedirs(in_path)
    out_path = os.path.join(working_path, "out")
    makedirs(out_path)
    gt_path = os.path.join(working_path, "ground_truth")
    makedirs(gt_path)

    cj.job.update(progress=1, statusComment="Downloading images...")
    image_instances = ImageInstanceCollection().fetch_with_filter("project", params.cytomine_id_project)
    input_images = [i for i in image_instances if gt_suffix not in i.originalFilename]
    gt_images = [i for i in image_instances if gt_suffix in i.originalFilename]

    for input_image in input_images:
        input_image.download(os.path.join(in_path, "{id}.tif"))

    for gt_image in gt_images:
        related_name = gt_image.originalFilename.replace(gt_suffix, '')
        related_image = [i for i in input_images if related_name == i.originalFilename]
        if len(related_image) == 1:
            gt_image.download(os.path.join(gt_path, "{}.tif".format(related_image[0].id)))

    cj.job.update(progress=25, statusComment="Launching workflow...")

    command = "/icy/run.sh {} {}".format(in_path, params.scale3sens)
    call(command, shell=True)

    cj.job.update(progress=60, statusComment="Extracting polygons...")

    for image in input_images:
        file = "{}.tif".format(image.id)
        path = os.path.join(out_path, file)

        data = io.imread(path)
        indexes = np.unique(data)
        loc = locator.BinaryLocator()
        objects = dict()

        for i, index in enumerate(indexes):
            if not index == 0:
                mask = (data == index).astype(np.uint8) * 255
                polygons = [polygon[0].buffer(2.0) for polygon in loc.locate(mask)]
                polygon = cascaded_union(polygons).buffer(-2.0)
                if not polygon.is_empty and polygon.area > 0:
                    objects[index] = polygon

        print("Found {} polygons in this image {}.".format(len(objects), image.id))

        # upload
        for index, polygon in objects.items():
            annotation = add_annotation(image, polygon)
            if annotation:
                Property(annotation, "index", str(index)).save()


    cj.job.update(progress=99, statusComment="Cleaning...")
    for image in input_images:
        os.remove(os.path.join(in_path, "{}.tif".format(image.id)))

    cj.job.update(status=Job.TERMINATED, progress=100, statusComment="Finished.")
