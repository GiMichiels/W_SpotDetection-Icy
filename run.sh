#fullpaths for lib, jar, protocol
#launch it from icy directory
java -cp icy/lib/ -jar icy/icy.jar -hl -x plugins.adufour.protocols.Protocols protocol="icy/proto/icy_brigth_spot_detections_batch.protocol" inputFolder="/data/in" extension=tif csvFileSuffix=_results scale3enable=true scale3sensitivity=40

#parameters can be exposed through read boxes in the icy protocols and identified with an id, here e.g. scale3enable